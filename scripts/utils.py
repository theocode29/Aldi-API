import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

from scripts import config, validators


def log_event(level: str, event: str, **fields) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": level, "event": event, **fields}
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    with (logs_dir / "scraper.log").open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "X-Algolia-API-Key": config.ALGOLIA_API_KEY or "",
            "X-Algolia-Application-Id": config.ALGOLIA_APP_ID or "",
            "Content-Type": "application/json",
            "User-Agent": "Aldi-API-Scraper/1.0",
        }
    )
    return session


def sleep_with_jitter() -> None:
    delay = random.uniform(config.PAGE_DELAY_MIN_MS / 1000.0, config.PAGE_DELAY_MAX_MS / 1000.0)
    time.sleep(delay)


def post_algolia_queries(session: requests.Session, body: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{config.ALGOLIA_HOST}/1/indexes/*/queries"
    response = session.post(url, json=body, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"Algolia request failed: {response.status_code} {response.text}")
    return response.json()


def get_first(mapping: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


class AldiScraper:
    def __init__(self):
        self.session = get_session()

    @staticmethod
    def _escape_filter_value(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"').strip()

    @staticmethod
    def _normalize_category(category: str) -> str:
        value = " ".join(str(category or "").strip().split())
        if not value:
            return ""
        value = value.replace("&", "et")
        value = value.replace("  ", " ")
        return value.strip()

    @staticmethod
    def _category_variants(category: str) -> List[str]:
        variants = set()
        cleaned = " ".join(str(category or "").strip().split())
        if not cleaned:
            return []

        variants.add(cleaned)
        variants.add(cleaned.replace("&", "et"))
        variants.add(cleaned.replace(" & ", " et "))
        variants.add(cleaned.replace("&", " et "))

        safe_variants = []
        for variant in variants:
            normalized = " ".join(str(variant).strip().split())
            if not normalized:
                continue
            if "&" in normalized:
                normalized = normalized.replace("&", "et")
            if normalized not in safe_variants:
                safe_variants.append(normalized)
        return safe_variants

    def _query_single_filter(self, index_name: str, filter_str: Optional[str] = None) -> List[Dict[str, Any]]:
        all_hits: List[Dict[str, Any]] = []
        page = 0

        while page < config.MAX_PAGES_SAFETY_LIMIT:
            try:
                params = f"hitsPerPage={config.HITS_PER_PAGE}&page={page}"
                if filter_str:
                    params += f"&filters={quote_plus(filter_str)}"

                body = {"requests": [{"indexName": index_name, "params": params}]}
                if page > 0:
                    sleep_with_jitter()

                payload = post_algolia_queries(self.session, body)
                result = payload.get("results", [{}])[0]
                page_hits = list(result.get("hits", []))
                nb_pages = int(result.get("nbPages", 1))

                if page_hits:
                    all_hits.extend(page_hits)

                if page >= nb_pages - 1 or len(page_hits) == 0:
                    break

                page += 1
            except Exception as exc:
                log_event(
                    "warning",
                    "filter_query_error",
                    index=index_name,
                    filter=filter_str or "none",
                    page=page,
                    error=str(exc),
                    partial_hits=len(all_hits),
                )
                break

        return all_hits

    def get_all_products_from_index(self, index_name: str) -> List[Dict[str, Any]]:
        if not config.USE_FILTERED_QUERIES:
            return self._query_single_filter(index_name, None)

        all_hits_dict: Dict[str, Dict[str, Any]] = {}
        log_event("info", "filtered_queries_start", index=index_name, filter_count=len(config.CATEGORY_FILTERS) + 1)
        seen_filters = set()

        for idx, category in enumerate(config.CATEGORY_FILTERS):
            variants = self._category_variants(category)
            for variant in variants:
                if variant in seen_filters:
                    continue
                seen_filters.add(variant)

                safe_variant = self._normalize_category(variant)
                filter_str = f'hierarchicalCategories.lvl3:"{self._escape_filter_value(safe_variant)}"'
                log_event(
                    "info",
                    "filter_query_start",
                    index=index_name,
                    filter_index=idx + 1,
                    total_filters=len(config.CATEGORY_FILTERS) + 1,
                    category=safe_variant,
                )
                try:
                    hits = self._query_single_filter(index_name, filter_str)
                    for hit in hits:
                        if not isinstance(hit, dict):
                            continue
                        object_id = hit.get("objectID")
                        if object_id is not None:
                            all_hits_dict[str(object_id)] = hit
                except Exception as exc:
                    log_event("warning", "filter_query_failed", index=index_name, category=safe_variant, error=str(exc))

                log_event(
                    "info",
                    "filter_query_complete",
                    index=index_name,
                    category=safe_variant,
                    hits_this_filter=len(hits) if "hits" in locals() else 0,
                    unique_total=len(all_hits_dict),
                )

        uncategorized_filter = "NOT hierarchicalCategories.lvl3:*"
        log_event(
            "info",
            "filter_query_start",
            index=index_name,
            filter_index=len(config.CATEGORY_FILTERS) + 1,
            total_filters=len(config.CATEGORY_FILTERS) + 1,
            category="UNCATEGORIZED",
        )
        try:
            uncategorized_hits = self._query_single_filter(index_name, uncategorized_filter)
            for hit in uncategorized_hits:
                if not isinstance(hit, dict):
                    continue
                object_id = hit.get("objectID")
                if object_id is not None:
                    all_hits_dict[str(object_id)] = hit
        except Exception as exc:
            log_event("warning", "uncategorized_filter_failed", index=index_name, error=str(exc))

        log_event(
            "info",
            "filter_query_complete",
            index=index_name,
            category="UNCATEGORIZED",
            hits_this_filter=len(uncategorized_hits) if "uncategorized_hits" in locals() else 0,
            unique_total=len(all_hits_dict),
        )

        all_hits = list(all_hits_dict.values())
        if not all_hits:
            log_event("warning", "filtered_queries_empty_fallback", index=index_name, fallback_used=True)
            all_hits = self._query_single_filter(index_name, None)

        log_event(
            "info",
            "filtered_queries_complete",
            index=index_name,
            total_unique_hits=len(all_hits),
            filters_executed=len(seen_filters) + 1,
        )

        if all_hits:
            validators.ensure_hits_have_required_keys(all_hits, ["objectID"])
        return all_hits

    def fetch(self) -> Dict[str, List[Dict[str, Any]]]:
        assortment = self.get_all_products_from_index(config.ASSORTMENT_INDEX)
        offers = self.get_all_products_from_index(config.OFFERS_INDEX)
        return {"assortment": assortment, "offers": offers}

    def extract_price(self, product: Dict[str, Any]) -> Any:
        v = get_first(product, ("price", "currentPrice", "current_price", "priceValue", "sales_price", "offer_price", "salesPrice"))
        if v is None:
            pf = get_first(product, ("priceFormatted",), default=None)
            if isinstance(pf, str):
                try:
                    return float(pf.replace(",", "."))
                except Exception:
                    return None
        return v

    def extract_name(self, product: Dict[str, Any]) -> str:
        return str(get_first(product, ("productName", "name", "title", "label"), default="") or "")

    def extract_image(self, product: Dict[str, Any]) -> Any:
        v = get_first(product, ("productPicture", "badgeRendition", "productPictureRenditions", "image_url", "image", "thumbnail", "mainImage", "images"))
        if isinstance(v, list) and v:
            return v[0]
        if isinstance(v, str):
            parts = v.split(",")
            first = parts[0].strip()
            return first.split()[0]
        return v

    def extract_unit(self, product: Dict[str, Any]) -> Any:
        return get_first(product, ("unit", "unitSize", "size", "quantity", "net_weight", "salesUnitFormatted", "salesUnit2"))

    def extract_valid_until(self, product: Dict[str, Any]) -> Any:
        return get_first(product, ("validUntil", "valid_to", "endDate", "promotion_end_date", "promo_end"))

    def extract_promo_text(self, product: Dict[str, Any]) -> Any:
        return get_first(product, ("promoText", "promotionText", "description", "subtitle", "shortDescription", "longDescription"))

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
        for key, category in mapping.items():
            if key in n:
                return category
        return "autres"

    def merge(self, assortment: List[Dict[str, Any]], offers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        products: Dict[str, Dict[str, Any]] = {}
        for item in assortment:
            pid = str(item.get("objectID"))
            base = dict(item)
            base["is_promotion"] = False
            base["promo_text"] = None
            base["valid_until"] = None
            price = self.extract_price(base)
            if price is not None:
                base["price"] = price
            products[pid] = base

        for item in offers:
            pid = str(item.get("objectID"))
            if pid not in products:
                products[pid] = dict(item)
            product = products[pid]
            offer_price = self.extract_price(item)
            if offer_price is not None:
                product["price"] = offer_price
            product["is_promotion"] = True
            product["promo_text"] = self.extract_promo_text(item)
            product["valid_until"] = self.extract_valid_until(item)
            product["source_offer"] = True
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

    def to_iso(self, value: Any) -> Any:
        if value is None:
            return None
        try:
            return str(value)
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
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)


def run() -> None:
    try:
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, lambda signum, frame: (_ for _ in ()).throw(TimeoutError("Global timeout reached")))
            signal.alarm(config.GLOBAL_TIMEOUT_SECONDS)
    except Exception:
        pass

    log_event("info", "scraper_start")
    scraper = AldiScraper()
    data = scraper.fetch()
    total = len(data.get("assortment", [])) + len(data.get("offers", []))
    if total == 0:
        log_event("warning", "zero_products_after_fetch", assortment=len(data.get("assortment", [])), offers=len(data.get("offers", [])))

    validators.validate_product_count(total, strict=False)
    merged = scraper.merge(data["assortment"], data["offers"])
    full = scraper.build_full(merged)
    minimal = scraper.build_min(merged)
    validators.validate_min_products(minimal["products"])

    scraper.save_json(full, "data/products.json")
    scraper.save_json(minimal, "data/products-min.json")

    meta = {
        "schema_version": full["meta"]["schema_version"],
        "last_updated": full["meta"]["last_updated"],
        "total_products": full["meta"]["total_products"],
    }
    with open("data/metadata.json", "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)

    log_event("info", "scraper_done", total=full["meta"]["total_products"])

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
