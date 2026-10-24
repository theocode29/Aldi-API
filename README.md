# 🛒 Aldi API - Product Scraper

> Automated scraper that generates static JSON files from ALDI Belgium's Algolia indices, deployed via GitHub Pages.

[![GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/theocode29/Aldi-API/actions)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 Overview

This project automatically scrapes ALDI Belgium product data from Algolia and publishes it as static JSON files. Perfect for building price comparison apps, product catalogs, or data analysis projects.

### 🎯 Key Features

- 🔄 **Automated Weekly Updates** - GitHub Actions runs the scraper every Sunday
- 📦 **Dual Format Output** - Full product data + minimal optimized version
- 🚀 **GitHub Pages Ready** - Static JSON served directly from repository
- ⚡ **Optimized Pagination** - Rate-limited requests with human-like delays
- 🛡️ **Robust Error Handling** - Partial result recovery on failures
- 📊 **Rich Logging** - Detailed progress tracking and diagnostics

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Valid Algolia API key for ALDI Belgium indices

### Installation

```bash
# Clone the repository
git clone https://github.com/theocode29/Aldi-API.git
cd Aldi-API

# Install dependencies
pip install -r requirements.txt

# Configure API key
export ALGOLIA_API_KEY="your_api_key_here"

# Run the scraper
python -m scripts.scraper
```

### Using `.env` File (Recommended)

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your API key
# ALGOLIA_API_KEY=your_actual_key

# Run scraper (environment loaded automatically)
python -m scripts.scraper
```

---

## 📄 Output Files

The scraper generates three JSON files in the `data/` directory:

| File | Description | Size | Use Case |
|------|-------------|------|----------|
| `products.json` | Complete product data with all Algolia fields | ~8 MB | Data analysis, debugging |
| `products-min.json` | Optimized with essential fields only | ~800 KB | Web apps, mobile apps |
| `metadata.json` | Summary metadata (version, timestamp, count) | <1 KB | Quick stats |

### Data Structure

#### `products.json`
```json
{
  "meta": {
    "schema_version": "1.0.0",
    "last_updated": "2025-11-22T19:15:02Z",
    "total_products": 1270,
    "source": "algolia",
    "indices": ["prod_be_fr_assortment", "prod_be_fr_offers"]
  },
  "products": [/* raw Algolia documents */]
}
```

#### `products-min.json`
```json
{
  "meta": { /* same as above */ },
  "products": [
    {
      "id": "12345",
      "name": "Produit Example",
      "price": 2.99,
      "category": "épicerie",
      "image_url": "https://...",
      "is_promotion": false,
      "promo_text": null,
      "valid_until": null,
      "unit": "500g"
    }
  ]
}
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALGOLIA_API_KEY` | *required* | Your Algolia search-only API key |
| `ALGOLIA_APP_ID` | `W297XVTVRZ` | Algolia application ID |
| `ASSORTMENT_INDEX` | `prod_be_fr_assortment` | Main products index |
| `OFFERS_INDEX` | `prod_be_fr_offers` | Promotions index |
| `HITS_PER_PAGE` | `1000` | Results per page (max 1000) |
| `PAGE_DELAY_MIN_MS` | `300` | Minimum delay between requests (ms) |
| `PAGE_DELAY_MAX_MS` | `900` | Maximum delay between requests (ms) |
| `MAX_PAGES_SAFETY_LIMIT` | `100` | Maximum pages to prevent infinite loops |
| `GLOBAL_TIMEOUT_SECONDS` | `300` | Global execution timeout |
| `MIN_PRODUCTS` | `400` | Minimum expected product count |
| `MAX_PRODUCTS` | `10000` | Maximum expected product count |

---

## 🔍 Pagination & Rate-Limiting

The scraper implements intelligent pagination with the following optimizations:

✅ **Human-like behavior** - Random delays (300-900ms) between requests  
✅ **Progressive logging** - Page number, cumulative count, totals  
✅ **Graceful failure** - Returns partial results on errors  
✅ **Safety limits** - Maximum 100 pages to prevent runaway loops

> [!IMPORTANT]
> **Algolia API Limitation**: The Search API has a **hard limit of 1000 results** per query, even with pagination. To bypass this:
> - Use the Browse API (requires different permissions)
> - Make multiple filtered queries (by category, price range, etc.)
>
> Current results: **~1270 products** (1000 from assortment + ~270 from offers)

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_scraper.py
```

---

## 🤖 CI/CD - GitHub Actions

The workflow automatically:
1. Runs every **Sunday at 1:00 AM UTC**
2. Checks Algolia API rate limits
3. Executes the scraper
4. Commits updated JSON files (if changed)
5. Validates output file sizes and counts

### Manual Trigger

Go to **Actions** → **🛒 Scrape ALDI Products** → **Run workflow**

### Required Secret

Add `ALGOLIA_API_KEY` in: **Settings → Secrets and variables → Actions**

---

## 🌐 GitHub Pages

### Setup

1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** / Folder: **/ (root)**
4. Save

### Access Your Data

```
https://YOUR_USERNAME.github.io/Aldi-API/data/products.json
https://YOUR_USERNAME.github.io/Aldi-API/data/products-min.json
https://YOUR_USERNAME.github.io/Aldi-API/data/metadata.json
```

---

## 📊 Usage Examples

### Quick Stats

```bash
# Total products
jq '.meta.total_products' data/products-min.json

# Count promotions
jq '[.products[] | select(.is_promotion)] | length' data/products-min.json

# Average price
jq '[.products[].price | select(. != null)] | add/length' data/products-min.json
```

### JavaScript Fetch

```javascript
const response = await fetch('https://YOUR_USERNAME.github.io/Aldi-API/data/products-min.json');
const data = await response.json();
console.log(`Total products: ${data.meta.total_products}`);
```

### Python Integration

```python
import requests

url = "https://YOUR_USERNAME.github.io/Aldi-API/data/products-min.json"
response = requests.get(url)
data = response.json()

# Filter dairy products
dairy = [p for p in data['products'] if p['category'] == 'produits laitiers']
print(f"Found {len(dairy)} dairy products")
```

---

## 🛠️ Development

### Project Structure

```
Aldi-API/
├── .github/
│   └── workflows/
│       └── scrape-aldi.yml    # CI/CD configuration
├── data/                       # Generated JSON files
│   ├── products.json
│   ├── products-min.json
│   └── metadata.json
├── scripts/
│   ├── config.py              # Configuration & environment
│   ├── scraper.py             # Main scraper logic
│   ├── utils.py               # Utilities (HTTP, logging)
│   └── validators.py          # Data validation
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
└── README.md                  # This file
```

### Local Publishing

```bash
# Make script executable
chmod +x scripts/publish.sh

# Run scraper + commit + push
./scripts/publish.sh
```

---

## 🐛 Troubleshooting

### `403 Forbidden` Error

**Cause**: Invalid or restricted API key

**Solutions**:
- Verify `ALGOLIA_API_KEY` is a search-only key
- Check key has access to specified indices
- Test with curl:
  ```bash
  curl -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" \
       -H "X-Algolia-Application-Id: W297XVTVRZ" \
       "https://W297XVTVRZ-dsn.algolia.net/1/indexes/*/queries"
  ```

### Missing Environment Variable

**Error**: `Missing ALGOLIA_API_KEY environment variable`

**Solution**: Ensure key is exported or defined in `.env` file

### Low Product Count

**Expected**: ~1270 products  
**Actual**: < 400 products

**Cause**: API connection issues or index changes  
**Solution**: Check GitHub Actions logs for detailed errors

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- ALDI Belgium for providing product data
- Algolia for the search infrastructure

---

## 📮 Contact

**Issues**: [GitHub Issues](https://github.com/theocode29/Aldi-API/issues)  
**Author**: [@theocode29](https://github.com/theocode29)

---

<div align="center">
  <sub>Built with ❤️ using Python & GitHub Actions</sub>
</div>