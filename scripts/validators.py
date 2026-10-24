from typing import Any, Dict, List

from . import config, utils


def ensure_hits_have_required_keys(hits: List[Dict[str, Any]], required: List[str]) -> None:
    for i, hit in enumerate(hits):
        for key in required:
            if key not in hit:
                utils.log_event("error", "missing_required_key", index=i, key=key)
                raise KeyError(f"Missing key {key} in hit {i}")


def validate_product_count(total: int, *, strict: bool = False) -> None:
    if total <= 0:
        if strict:
            utils.log_event("error", "invalid_product_count", total=total, min=config.MIN_PRODUCTS, max=config.MAX_PRODUCTS)
            raise ValueError(f"Product count {total} out of expected range")
        utils.log_event("warning", "empty_product_count", total=total)
        return

    if total < config.MIN_PRODUCTS:
        if strict:
            utils.log_event("error", "invalid_product_count", total=total, min=config.MIN_PRODUCTS, max=config.MAX_PRODUCTS)
            raise ValueError(f"Product count {total} out of expected range")
        utils.log_event("warning", "low_product_count", total=total, min=config.MIN_PRODUCTS)
        return

    if total > config.MAX_PRODUCTS:
        if strict:
            utils.log_event("error", "invalid_product_count", total=total, min=config.MIN_PRODUCTS, max=config.MAX_PRODUCTS)
            raise ValueError(f"Product count {total} out of expected range")
        utils.log_event("warning", "high_product_count", total=total, max=config.MAX_PRODUCTS)


def validate_min_products(products: List[Dict[str, Any]]) -> None:
    required_top = ["id", "name", "category", "is_promotion"]
    if not products:
        utils.log_event("warning", "empty_min_products")
        return

    for i, product in enumerate(products):
        for key in required_top:
            if key not in product:
                utils.log_event("error", "min_product_missing_key", index=i, key=key)
                raise KeyError(f"Missing minimal key {key} in product {i}")
