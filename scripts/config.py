import os
from pathlib import Path

# Charge automatiquement les variables depuis .env s'il existe,
# sans écraser celles déjà présentes dans l'environnement.
def _load_env_file() -> None:
    try:
        env_path = Path(".env")
        if not env_path.exists():
            return
        with env_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                if key not in os.environ:
                    os.environ[key] = val
    except Exception:
        # Ne pas bloquer si .env est invalide; on utilisera les valeurs d'environnement existantes
        pass

_load_env_file()

ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID", "W297XVTVRZ")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
if ALGOLIA_API_KEY is None:
    raise RuntimeError("Missing ALGOLIA_API_KEY environment variable.")

ALGOLIA_HOST = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net"

ASSORTMENT_INDEX = os.getenv("ASSORTMENT_INDEX", "prod_be_fr_assortment")
OFFERS_INDEX = os.getenv("OFFERS_INDEX", "prod_be_fr_offers")

HITS_PER_PAGE = int(os.getenv("HITS_PER_PAGE", "1000"))
GLOBAL_TIMEOUT_SECONDS = int(os.getenv("GLOBAL_TIMEOUT_SECONDS", "300"))

MIN_PRODUCTS = int(os.getenv("MIN_PRODUCTS", "400"))
MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "10000"))

SCHEMA_VERSION = os.getenv("SCHEMA_VERSION", "1.0.0")