import os
from pathlib import Path


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

PAGE_DELAY_MIN_MS = int(os.getenv("PAGE_DELAY_MIN_MS", "300"))
PAGE_DELAY_MAX_MS = int(os.getenv("PAGE_DELAY_MAX_MS", "900"))
MAX_PAGES_SAFETY_LIMIT = int(os.getenv("MAX_PAGES_SAFETY_LIMIT", "100"))

USE_FILTERED_QUERIES = os.getenv("USE_FILTERED_QUERIES", "true").lower() == "true"

CATEGORY_FILTERS = [
    "Collations et sucreries",
    "Viande",
    "Produits laitiers et fromages",
    "Plats préparés",
    "Légumes frais",
    "Boissons non alcoolisées",
    "Boissons alcoolisées",
    "Fruits frais",
    "Végétarien et végétalien",
    "Conserves",
    "Pâtisserie et cuisine",
    "Poissons et fruits de mer",
    "Poissons et fruits de la mer",
    "Pain et pâtisseries",
    "Cartes-cadeau et cartes prépayées",
    "Produits cosmétiques et soins",
    "Aliments pour animaux",
    "Ménage",
    "Café, thé, cacao",
    "Produits à tartiner",
    "Des glaces à prix discount",
    "Pâtes et riz",
    "Fleurs fraîches",
]
