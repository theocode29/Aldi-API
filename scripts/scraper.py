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

    def _query_single_filter(self, index_name: str, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query a single filter and return all results with pagination.
        """
        all_hits: List[Dict[str, Any]] = []
        page = 0
        
        while page < config.MAX_PAGES_SAFETY_LIMIT:
            try:
                # Prepare paginated request with optional filter
                params = f"hitsPerPage={config.HITS_PER_PAGE}&page={page}"
                if filter_str:
                    params += f"&filters={filter_str}"
                
                body = {"requests": [{"indexName": index_name, "params": params}]}
                
                # Add delay before request (except for first page)
                if page > 0:
                    utils.sleep_with_jitter()
                
                # Execute request
                data = utils.post_algolia_queries(self.session, body)
                res = data.get("results", [{}])[0]
                page_hits = list(res.get("hits", []))
                nb_pages = int(res.get("nbPages", 1))
                
                # Update cumulative results
                all_hits.extend(page_hits)
                
                # Check if we've retrieved all pages
                if page >= nb_pages - 1 or len(page_hits) == 0:
                    break
                
                page += 1
                
            except Exception as e:
                utils.log_event(
                    "warning",
                    "filter_query_error",
                    index=index_name,
                    filter=filter_str or "none",
                    page=page,
                    error=str(e),
                    partial_hits=len(all_hits)
                )
                break
        
        return all_hits

    def get_all_products_from_index(self, index_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve all products from an Algolia index.
        
        If USE_FILTERED_QUERIES is enabled, makes multiple filtered queries
        to bypass the 1000-result limit, otherwise uses standard pagination.
        
        Features:
        - Multiple category-filtered queries (if enabled)
        - Deduplication by objectID
        - Human-like delays between requests (300-900ms)
        - Progressive logging with cumulative counts
        - Robust error handling with partial result recovery
        """
        if not config.USE_FILTERED_QUERIES:
            # Use original pagination logic (single query, max 1000 results)
            return self._query_single_filter(index_name, None)
        
        # Filtered query strategy
        all_hits_dict: Dict[str, Dict[str, Any]] = {}  # Deduplicate by objectID
        
        utils.log_event("info", "filtered_queries_start", index=index_name, filter_count=len(config.CATEGORY_FILTERS) + 1)
        
        # Query each category filter
        for idx, category in enumerate(config.CATEGORY_FILTERS):
            filter_str = f'hierarchicalCategories.lvl3:"{category}"'
            
            utils.log_event(
                "info",
                "filter_query_start",
                index=index_name,
                filter_index=idx + 1,
                total_filters=len(config.CATEGORY_FILTERS) + 1,
                category=category
            )
            
            hits = self._query_single_filter(index_name, filter_str)
            
            # Add to deduplication dict
            for hit in hits:
                all_hits_dict[hit['objectID']] = hit
            
            utils.log_event(
                "info",
                "filter_query_complete",
                index=index_name,
                category=category,
                hits_this_filter=len(hits),
                unique_total=len(all_hits_dict)
            )
        
        # Query uncategorized products (no lvl3)
        utils.log_event(
            "info",
            "filter_query_start",
            index=index_name,
            filter_index=len(config.CATEGORY_FILTERS) + 1,
            total_filters=len(config.CATEGORY_FILTERS) + 1,
            category="UNCATEGORIZED"
        )
        
        uncategorized_filter = "NOT hierarchicalCategories.lvl3:*"
        uncategorized_hits = self._query_single_filter(index_name, uncategorized_filter)
        
        for hit in uncategorized_hits:
            all_hits_dict[hit['objectID']] = hit
        
        utils.log_event(
            "info",
            "filter_query_complete",
            index=index_name,
            category="UNCATEGORIZED",
            hits_this_filter=len(uncategorized_hits),
            unique_total=len(all_hits_dict)
        )
        
        # Convert to list
        all_hits = list(all_hits_dict.values())
        
        utils.log_event(
            "info",
            "filtered_queries_complete",
            index=index_name,
            total_unique_hits=len(all_hits),
            filters_executed=len(config.CATEGORY_FILTERS) + 1
        )
        
        validators.ensure_hits_have_required_keys(all_hits, ["objectID"])
        return all_hits

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