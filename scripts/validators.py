from typing import List, Dict, Any

from . import config, utils


def ensure_hits_have_required_keys(hits: List[Dict[str, Any]], required: List[str]) -> None:
    for i, h in enumerate(hits):
        for key in required:
            if key not in h:
                utils.log_event("error", "missing_required_key", index=i, key=key)
                raise KeyError(f"Missing key {key} in hit {i}")


def validate_product_count(total: int) -> None:
    if total < config.MIN_PRODUCTS or total > config.MAX_PRODUCTS:
        utils.log_event("error", "invalid_product_count", total=total, min=config.MIN_PRODUCTS, max=config.MAX_PRODUCTS)
        raise ValueError(f"Product count {total} out of expected range")


def validate_min_products(products: List[Dict[str, Any]]) -> None:
    required_top = ["id", "name", "category", "is_promotion"]
    for i, p in enumerate(products):
        for key in required_top:
            if key not in p:
                utils.log_event("error", "min_product_missing_key", index=i, key=key)
                raise KeyError(f"Missing minimal key {key} in product {i}")