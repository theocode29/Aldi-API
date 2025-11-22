import os
import sys
import json
import signal
from datetime import datetime, timezone
from typing import List, Dict, Any

from scripts import config, utils, validators


def _timeout_handler(signum, frame):
    raise TimeoutError("Global timeout reached")


class AldiScraper:
    def __init__(self):
        self.session = utils.get_session()

    def get_all_products_from_index(self, index_name: str) -> List[Dict[str, Any]]:
        utils.log_event("info", "browse_index_start", index=index_name)
        hits = utils.browse_algolia_index(self.session, index_name)
        utils.log_event("info", "browse_index_done", index=index_name, hits=len(hits))
        validators.ensure_hits_have_required_keys(hits, ["objectID"])
        return hits

    def fetch(self) -> Dict[str, List[Dict[str, Any]]]:
        assortment = self.get_all_products_from_index(config.ASSORTMENT_INDEX)
        offers = self.get_all_products_from_index(config.OFFERS_INDEX)
        return {"assortment": assortment, "offers": offers}

    def extract_price(self, d: Dict[str, Any]) -> Any:
        # Algolia Aldi: prix souvent sous "salesPrice" (numérique) ou "priceFormatted" (string)
        v = utils.get_first(d, ("price", "currentPrice", "current_price", "priceValue", "sales_price", "offer_price", "salesPrice"))
        if v is None:
            pf = utils.get_first(d, ("priceFormatted",), default=None)
            if isinstance(pf, str):
                try:
                    return float(pf.replace(",", "."))
                except Exception:
                    return None
        return v

    def extract_name(self, d: Dict[str, Any]) -> str:
        return utils.get_first(d, ("productName", "name", "title", "label"), default="")

    def extract_image(self, d: Dict[str, Any]) -> Any:
        # Essayer d'abord les champs spécifiques Algolia
        v = utils.get_first(d, ("productPicture", "badgeRendition", "productPictureRenditions", "image_url", "image", "thumbnail", "mainImage", "images"))
        if isinstance(v, list) and v:
            return v[0]
        # Si c'est une string de renditions séparées par des virgules/espaces, prendre le premier URL
        if isinstance(v, str):
            # Extraire l'URL initial avant les espaces/virgules
            parts = v.split(",")
            first = parts[0].strip()
            # Certaines entrées contiennent "url 288w" -> ne garder que l'URL
            return first.split()[0]
        return v

    def extract_unit(self, d: Dict[str, Any]) -> Any:
        return utils.get_first(d, ("unit", "unitSize", "size", "quantity", "net_weight", "salesUnitFormatted", "salesUnit2"))

    def extract_valid_until(self, d: Dict[str, Any]) -> Any:
        return utils.get_first(d, ("validUntil", "valid_to", "endDate", "promotion_end_date", "promo_end"))

    def extract_promo_text(self, d: Dict[str, Any]) -> Any:
        v = utils.get_first(d, ("promoText", "promotionText", "description", "subtitle", "shortDescription", "longDescription"))
        # Certaines descriptions sont en HTML -> renvoyer tel quel (min.json reste simple)
        return v

    def categorize(self, name: str) -> str:
        n = name.lower()
        mapping = {
            "lait": "produits laitiers",
            "yaourt": "produits laitiers",
            "fromage": "fromages",
            "gouda": "fromages",
            "cheddar": "fromages",
            "poulet": "viandes",
            "boeuf": "viandes",
            "porc": "viandes",
            "pain": "boulangerie",
            "baguette": "boulangerie",
            "pâtes": "épicerie",
            "riz": "épicerie",
            "huile": "épicerie",
            "tomate": "légumes",
            "banane": "fruits",
            "pomme": "fruits",
            "saumon": "poisson",
            "thon": "poisson",
        }
        for k, cat in mapping.items():
            if k in n:
                return cat
        return "autres"

    def merge(self, assortment: List[Dict[str, Any]], offers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        products: Dict[str, Dict[str, Any]] = {}
        for h in assortment:
            pid = str(h.get("objectID"))
            base = dict(h)
            base["is_promotion"] = False
            base["promo_text"] = None
            base["valid_until"] = None
            price = self.extract_price(base)
            if price is not None:
                base["price"] = price
            products[pid] = base
        for h in offers:
            pid = str(h.get("objectID"))
            if pid not in products:
                products[pid] = dict(h)
            p = products[pid]
            offer_price = self.extract_price(h)
            if offer_price is not None:
                p["price"] = offer_price
            p["is_promotion"] = True
            p["promo_text"] = self.extract_promo_text(h)
            p["valid_until"] = self.extract_valid_until(h)
            p["source_offer"] = True
        return products

    def build_full(self, products: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        meta = {
            "schema_version": config.SCHEMA_VERSION,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_products": len(products),
            "source": "algolia",
            "indices": [config.ASSORTMENT_INDEX, config.OFFERS_INDEX],
        }
        return {"meta": meta, "products": list(products.values())}

    def to_iso(self, v: Any) -> Any:
        if v is None:
            return None
        try:
            return str(v)
        except Exception:
            return None

    def build_min(self, products: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for pid, raw in products.items():
            name = self.extract_name(raw) or ""
            item = {
                "id": pid,
                "name": name,
                "price": self.extract_price(raw),
                "category": self.categorize(name),
                "image_url": self.extract_image(raw),
                "is_promotion": bool(raw.get("is_promotion", False)),
                "promo_text": self.extract_promo_text(raw),
                "valid_until": self.to_iso(raw.get("valid_until")),
                "unit": self.extract_unit(raw),
            }
            items.append(item)
        meta = {
            "schema_version": config.SCHEMA_VERSION,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_products": len(items),
        }
        return {"meta": meta, "products": items}

    def save_json(self, data: Dict[str, Any], path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def run():
    try:
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(config.GLOBAL_TIMEOUT_SECONDS)
    except Exception:
        pass

    utils.log_event("info", "scraper_start")
    sc = AldiScraper()
    data = sc.fetch()
    validators.validate_product_count(len(data["assortment"]) + len(data["offers"]))
    merged = sc.merge(data["assortment"], data["offers"])
    full = sc.build_full(merged)
    minimal = sc.build_min(merged)
    validators.validate_min_products(minimal["products"])
    os.makedirs("data", exist_ok=True)
    sc.save_json(full, "data/products.json")
    sc.save_json(minimal, "data/products-min.json")
    meta = {
        "schema_version": full["meta"]["schema_version"],
        "last_updated": full["meta"]["last_updated"],
        "total_products": full["meta"]["total_products"],
    }
    with open("data/metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    utils.log_event("info", "scraper_done", total=full["meta"]["total_products"])

    try:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
    except Exception:
        pass


if __name__ == "__main__":
    if "--dump-mock" in sys.argv:
        mock = {"results": [{"hits": [{"objectID": "123", "productName": "Gouda Jeune", "price": 1.49, "image": "https://example/image.jpg", "unit": "250 g"}]}]}
        print(json.dumps(mock, ensure_ascii=False, indent=2))
    else:
        run()