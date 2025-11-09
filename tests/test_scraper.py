import os
import responses
import pytest

# Assurer la présence de la clé avant l'import des modules
os.environ.setdefault("ALGOLIA_API_KEY", "test")

from scripts.scraper import AldiScraper
from scripts import config


@pytest.fixture(autouse=True)
def set_env():
    # Redonder pour toute fonction de test
    os.environ.setdefault("ALGOLIA_API_KEY", "test")


@responses.activate
def test_get_all_products_from_index():
    url = f"https://{config.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"
    responses.add(
        responses.POST,
        url,
        json={"results": [{"hits": [{"objectID": "123", "productName": "Gouda Jeune"}], "nbPages": 1}]},
        status=200,
    )
    sc = AldiScraper()
    hits = sc.get_all_products_from_index("assortment")
    assert len(hits) == 1
    assert hits[0]["objectID"] == "123"


def test_merge_promotions_override_price():
    sc = AldiScraper()
    assortment = [{"objectID": "A1", "productName": "Pain", "price": 2.0}]
    offers = [{"objectID": "A1", "promoText": "Promo", "price": 1.5}]
    merged = sc.merge(assortment, offers)
    assert merged["A1"]["is_promotion"] is True
    assert merged["A1"]["price"] == 1.5