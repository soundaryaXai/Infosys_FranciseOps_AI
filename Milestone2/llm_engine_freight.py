"""
llm_engine_freight.py — FreightQuote AI Copilot (Qwen2.5-3B-Instruct, 4-bit NF4).

Adapted from the mentor's llm_engine.py — same loading strategy (4-bit
NF4 quantization, sdpa->eager fallback, background warmup thread) — but
rebuilt around this assignment's 3 agents (Section 8) and with one real
addition the base template didn't have: every generation entry point is
wrapped so a missing GPU/bitsandbytes/HF access degrades to a rule-based
answer instead of crashing the Copilot page. Section 8 explicitly expects
this fallback ("Otherwise you'll see a rule-based fallback — expected
behavior, not a bug"), so it needs to actually exist, not just be assumed.
"""
import os
import json
import re
import threading

import config

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
CACHE_DIR = os.path.join(config.MODELS_DIR, "hf_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

_model = None
_tokenizer = None
_load_lock = threading.Lock()
_load_failed = False


def get_model():
    """Loads (and caches) the quantized model. Raises on failure — callers
    should go through _safe_run()/the public functions below, which catch
    this and fall back, rather than calling get_model() directly."""
    global _model, _tokenizer, _load_failed
    if _model is not None:
        return _model, _tokenizer
    with _load_lock:
        if _model is not None:
            return _model, _tokenizer
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

        bnb = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
        )
        kw = {"token": config.HF_TOKEN, "cache_dir": CACHE_DIR} if config.HF_TOKEN else {"cache_dir": CACHE_DIR}
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, **kw)
        try:
            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, quantization_config=bnb, device_map="auto",
                torch_dtype=torch.float16, low_cpu_mem_usage=True,
                attn_implementation="sdpa", **kw,
            )
        except Exception:
            _model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, quantization_config=bnb, device_map="auto",
                torch_dtype=torch.float16, low_cpu_mem_usage=True,
                attn_implementation="eager", **kw,
            )
        _model.eval()
        _load_failed = False
    return _model, _tokenizer


def warmup_llm():
    global _load_failed
    try:
        get_model()
        return _model is not None
    except Exception as e:
        _load_failed = True
        print(f"LLM warmup failed, will use rule-based fallback: {e}")
        return False


def is_llm_loaded():
    return _model is not None


_warmup_thread_started = False


def start_background_warmup():
    global _warmup_thread_started
    if _warmup_thread_started:
        return
    _warmup_thread_started = True
    threading.Thread(target=warmup_llm, daemon=True).start()


def _run(msgs, max_tokens=100, greedy=True):
    import torch
    model, tok = get_model()
    tmpl = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok(tmpl, return_tensors="pt").to(model.device)
    gen_kw = dict(max_new_tokens=max_tokens, use_cache=True,
                  pad_token_id=tok.eos_token_id, eos_token_id=tok.eos_token_id)
    if greedy:
        gen_kw["do_sample"] = False
    else:
        gen_kw.update(do_sample=True, temperature=0.2, top_p=0.9)
    with torch.inference_mode():
        out = model.generate(**inputs, **gen_kw)
    return tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()


def _safe_run(msgs, max_tokens=100, greedy=True):
    """Returns (text, used_llm: bool). Never raises."""
    try:
        return _run(msgs, max_tokens=max_tokens, greedy=greedy), True
    except Exception as e:
        print(f"LLM generation unavailable, using rule-based fallback: {e}")
        return None, False


# ────────────────────────────────────────────────────────────────
# Agent roles — Section 8 / Phase 3
# ────────────────────────────────────────────────────────────────
AGENT_ROLES = {
    "agent1": ("Dynamic Pricing Agent",
               "You specialise in freight cost estimation from weight, distance, and port congestion."),
    "agent2": ("Route Delay Classifier Agent",
               "You specialise in shipment delay risk from transit times, congestion, and weather."),
    "agent3": ("Carrier Compliance Sentinel Agent",
               "You specialise in carrier reliability, safety violations, and audit risk."),
}


# ────────────────────────────────────────────────────────────────
# Rule-based fallbacks — built directly from the agent context dicts
# that agents_freight.py already populates, so they're always sensible
# even with zero GPU/LLM available.
# ────────────────────────────────────────────────────────────────
def _fallback_agent_lines(a1, a2, a3):
    cost = a1.get("predicted_cost_usd")
    delay_p = a2.get("delay_probability")
    risk = a3.get("risk_score")
    line1 = (f"Estimated freight cost is ${cost:,.2f} for this shipment profile."
             if cost is not None else "No pricing data available yet — run Agent 1 first.")
    line2 = (f"Delay probability is {delay_p*100:.1f}% ({a2.get('risk_label', 'unclassified')})."
             if delay_p is not None else "No route-delay data available yet — run Agent 2 first.")
    line3 = (f"Carrier compliance risk is {risk*100:.1f}% ({a3.get('status', 'unclassified')})."
             if risk is not None else "No carrier-compliance data available yet — run Agent 3 first.")
    return line1, line2, line3


def _fallback_synthesis(a1, a2, a3):
    l1, l2, l3 = _fallback_agent_lines(a1, a2, a3)
    concerns = []
    if a2.get("delay_probability", 0) > 0.5:
        concerns.append("elevated delay risk")
    if a3.get("risk_score", 0) > 0.5:
        concerns.append("carrier compliance concerns")
    verdict = ("Proceed with standard monitoring." if not concerns
               else f"Flag for manual review due to {' and '.join(concerns)}.")
    return f"{l1} {l2} {l3} {verdict}"


def generate_debate_and_synthesis(user_query, agent1_context, agent2_context, agent3_context, db_stats=None):
    system_prompt = (
        "You are the FreightQuote AI Multi-Agent Engine. "
        "Analyze the query and all data. Reply STRICTLY in this format:\n"
        "[AGENT 1]: <1 bullet on pricing>\n"
        "[AGENT 2]: <1 bullet on route delay risk>\n"
        "[AGENT 3]: <1 bullet on carrier compliance>\n"
        "[SYNTHESIS]: <2 sentences executive recommendation>"
    )
    ctx = (f"QUERY: {user_query}\nA1: {json.dumps(agent1_context)}\n"
           f"A2: {json.dumps(agent2_context)}\nA3: {json.dumps(agent3_context)}")
    if db_stats:
        ctx += f"\nDB: {json.dumps(db_stats)}"

    raw, used_llm = _safe_run(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": ctx}],
        max_tokens=120, greedy=True,
    )

    l1, l2, l3 = _fallback_agent_lines(agent1_context, agent2_context, agent3_context)
    res = {"agent1": l1, "agent2": l2, "agent3": l3,
           "synthesis": raw if used_llm else _fallback_synthesis(agent1_context, agent2_context, agent3_context)}

    if used_llm:
        for key, tag, nxt in [("agent1", "AGENT 1", "AGENT 2"),
                               ("agent2", "AGENT 2", "AGENT 3"),
                               ("agent3", "AGENT 3", "SYNTHESIS")]:
            m = re.search(rf"\[{tag}\]:\s*(.*?)(?=\[{nxt}\]|\Z)", raw, re.DOTALL | re.IGNORECASE)
            if m:
                res[key] = m.group(1).strip()
        m = re.search(r"\[SYNTHESIS\]:\s*(.*)", raw, re.DOTALL | re.IGNORECASE)
        if m:
            res["synthesis"] = m.group(1).strip()
    return res


def orchestrate_3_agents_query(user_question, agent1_context, agent2_context, agent3_context, db_stats=None):
    sys_p = ("You are FreightQuote AI Orchestrator. "
             "Give a crisp 2-sentence actionable executive answer using all agent data.")
    ctx = (f"QUERY: {user_question}\nA1: {json.dumps(agent1_context)}\n"
           f"A2: {json.dumps(agent2_context)}\nA3: {json.dumps(agent3_context)}")
    if db_stats:
        ctx += f"\nDB: {json.dumps(db_stats)}"
    raw, used_llm = _safe_run(
        [{"role": "system", "content": sys_p}, {"role": "user", "content": ctx}],
        max_tokens=100, greedy=True,
    )
    return raw if used_llm else _fallback_synthesis(agent1_context, agent2_context, agent3_context)


def generate_json(prompt, schema_keys=None):
    """Structured JSON generation, with a rule-based JSON fallback if the LLM is unavailable."""
    sys_p = "You are a freight intelligence engine. Respond ONLY with a valid JSON object."
    if schema_keys:
        sys_p += f" Required keys: {', '.join(schema_keys)}."
    raw, used_llm = _safe_run(
        [{"role": "system", "content": sys_p}, {"role": "user", "content": prompt}],
        max_tokens=150, greedy=True,
    )
    if not used_llm:
        return {k: "unavailable (LLM not loaded)" for k in (schema_keys or ["result"])}

    def _repair_json(text):
        text = re.sub(r'```json\s*|\s*```', '', text)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        text = re.sub(r'(["]|\d|true|false)\s*\n\s*(["\w]+":)', r'\1,\n\2', text)
        text = re.sub(r'(["]|\d|true|false)\s+(["\w]+":)', r'\1, \2', text)
        text = re.sub(r',\s*\}', '}', text)
        return text

    try:
        return json.loads(_repair_json(raw))
    except Exception:
        if schema_keys:
            out = {}
            for k in schema_keys:
                km = re.search(rf'"{k}"\s*:\s*"([^"]*)"|"{k}"\s*:\s*([^,\}}]+)', raw)
                out[k] = (km.group(1) if km and km.group(1) is not None else
                          km.group(2).strip() if km else "N/A")
            if any(v != "N/A" for v in out.values()):
                return out
        return {"error": "JSON parse failed", "raw": raw}


def generate_audit_action(agent1_context, agent2_context, agent3_context):
    """
    Phase 3 / Section 8 requirement: synthesize the 3 agents' numeric
    outputs into a structured JSON audit action.
    """
    prompt = (
        f"Shipment pricing: {json.dumps(agent1_context)}. "
        f"Route delay risk: {json.dumps(agent2_context)}. "
        f"Carrier compliance: {json.dumps(agent3_context)}. "
        "Produce a JSON audit action for this shipment."
    )
    schema = ["audit_flag", "risk_level", "recommended_action", "notes"]
    result = generate_json(prompt, schema)

    # Rule-based JSON fallback filled from real numbers, not the generic
    # "unavailable" placeholder generate_json() returns with no context.
    if result.get(schema[0]) == "unavailable (LLM not loaded)":
        delay_p = agent2_context.get("delay_probability", 0)
        risk = agent3_context.get("risk_score", 0)
        flagged = delay_p > 0.5 or risk > 0.5
        result = {
            "audit_flag": bool(flagged),
            "risk_level": "High" if flagged else "Low",
            "recommended_action": ("Escalate for manual carrier review" if flagged
                                    else "Proceed with standard processing"),
            "notes": "Rule-based fallback — LLM not loaded for this session.",
        }
    return result
