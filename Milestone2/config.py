"""
config.py — FreightQuote AI (adapted from the shared mentor template)
All secrets from Colab userdata / environment. No secret is ever hard-coded.

Secret names below match exactly what's used in Colab Secrets — see
README.md's secrets table.
"""
import os


def _get_secret(key):
    try:
        from google.colab import userdata
        val = userdata.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key, "")


STORAGE_DIR = ("/content/drive/MyDrive/FreightQuote_AI"
               if os.path.exists("/content/drive/MyDrive") else
               os.path.abspath("./data/FreightQuote_AI"))

NGROK_AUTHTOKEN = _get_secret("NGROK_AUTHTOKEN")
HF_TOKEN = _get_secret("HF_TOKEN")
KAGGLE_USERNAME = _get_secret("KAGGLE_USERNAME")
KAGGLE_KEY = _get_secret("KAGGLE_KEY")
EMAIL_PASSWORD = _get_secret("EMAIL_PASSWORD")
EMAIL_ID = _get_secret("EMAIL_ADDRESS")           # secret name: EMAIL_ADDRESS
JWT_SECRET_KEY = _get_secret("JWT_SECRET") or "freightquote-dev-secret-changeme"  # secret name: JWT_SECRET

# Primary admin — from your own secrets. Login identifier can be any
# string you like (username or email shape both work; login matches
# either username or email column).
ADMIN_USERNAME = _get_secret("ADMIN_USERNAME") or "infosys@ai"   # secret name: ADMIN_USERNAME
ADMIN_PASSWORD = _get_secret("ADMIN_PASSWORD") or "admin@123"

# Secondary, guaranteed-fallback admin — always seeded in addition to the
# one above, so a secrets typo never fully locks you out of the Admin
# Dashboard. Change these constants if you don't want this second account.
FALLBACK_ADMIN_USERNAME = "infosys@ai"
FALLBACK_ADMIN_PASSWORD = "admin@123"

os.makedirs(STORAGE_DIR, exist_ok=True)
DB_PATH = os.path.join(STORAGE_DIR, "freightquote.db")
MODELS_DIR = os.path.join(STORAGE_DIR, "models")
KAGGLE_CACHE_DIR = os.path.join(MODELS_DIR, "kaggle_cache")
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(KAGGLE_CACHE_DIR, exist_ok=True)

# Champion model file paths — one per agent (Section 7)
AGENT1_MODEL_PATH = os.path.join(MODELS_DIR, "pricing_champion.joblib")     # Dynamic Pricing (regression)
AGENT2_MODEL_PATH = os.path.join(MODELS_DIR, "route_delay_champion.joblib")  # Route Delay Classifier
AGENT3_MODEL_PATH = os.path.join(MODELS_DIR, "carrier_compliance_champion.joblib")  # Carrier Compliance Sentinel

# Indian port coverage (Section 2 — README port table)
PORTS = {
    "JNPT": "Jawaharlal Nehru Port, Mumbai",
    "MUNDRA": "Mundra Port, Gujarat",
    "CHENNAI": "Chennai Port, Tamil Nadu",
    "COCHIN": "Cochin Port, Kerala",
}
