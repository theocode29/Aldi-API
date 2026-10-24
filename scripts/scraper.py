import json
import sys

from scripts.utils import AldiScraper, run


if __name__ == "__main__":
    if "--dump-mock" in sys.argv:
        mock = {"results": [{"hits": [{"objectID": "123", "productName": "Gouda Jeune", "price": 1.49, "image": "https://example/image.jpg", "unit": "250 g"}]}]}
        print(json.dumps(mock, ensure_ascii=False, indent=2))
    else:
        run()
