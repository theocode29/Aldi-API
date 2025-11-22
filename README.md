# Aldi Scraper vers JSON statique (GitHub Pages)

- Génère `data/products.json` (complet) et `data/products-min.json` (minimal) à partir des indices Algolia d'ALDI Belgique.
- Pipeline automatisé via GitHub Actions (hebdomadaire), commits uniquement si modifications.

## Setup local
- Prérequis: Python `3.10+`, `pip`, accès réseau.
- Installer les dépendances: `python3 -m pip install -r requirements.txt`
- Configurer l’accès Algolia:
  - Obligatoire: `export ALGOLIA_API_KEY="<votre_clef>"`
  - Optionnel (valeurs par défaut déjà intégrées):
    - `export ALGOLIA_APP_ID="W297XVTVRZ"`
    - `export ASSORTMENT_INDEX="prod_be_fr_assortment"`
    - `export OFFERS_INDEX="prod_be_fr_offers"`
    - `export HITS_PER_PAGE=1000` (pour paginer plus ou moins)
    - `export GLOBAL_TIMEOUT_SECONDS=300`
    - `export PAGE_DELAY_MIN_MS=300` (délai minimum entre requêtes, en ms)
    - `export PAGE_DELAY_MAX_MS=900` (délai maximum entre requêtes, en ms)
    - `export MAX_PAGES_SAFETY_LIMIT=100` (limite de sécurité anti-boucle infinie)
- Lancer en module: `python3 -m scripts.scraper`
- Alternative: `python scripts/scraper.py`

Astuce: vous pouvez créer un fichier `.env` à la racine; le scraper le charge automatiquement s'il existe. En production/CI, utilisez des variables d'environnement.

Utiliser `.env` (recommandé en local):
- Copier l’exemple: `cp .env.example .env`
- Éditer `ALGOLIA_API_KEY=...` (et, si besoin, `ALGOLIA_APP_ID`, `ASSORTMENT_INDEX`, `OFFERS_INDEX`)
- Lancer ensuite `python3 -m scripts.scraper` (les valeurs de `.env` seront prises en compte)

## Tests
- `pytest -q`

## Secrets
- Dans GitHub → Settings → Actions → Secrets: ajouter `ALGOLIA_API_KEY`.

## Fichiers générés
- `data/products.json` (complet, avec meta)
- `data/products-min.json` (essential fields)
- `data/metadata.json` (meta résumé)

## Où trouver et comment lire les résultats
- `data/products.json` (complet)
  - `meta.schema_version`: version du schéma.
  - `meta.last_updated`: ISO datetime UTC de la génération.
  - `meta.total_products`: nombre total d’articles fusionnés.
  - `meta.source`: source (`algolia`).
  - `meta.indices`: indices interrogés (`assortment`, `offers`).
  - `products`: tableau des documents bruts (champs Algolia tels que `objectID`, `productName`, `salesPrice`, `productPicture`, etc.).
- `data/products-min.json` (simplifié)
  - `products[]` contient des champs uniformisés pour l’usage courant:
    - `id`: identifiant (depuis `objectID`).
    - `name`: nom produit (depuis `productName`/`name`).
    - `price`: prix numérique si disponible (priorité à `salesPrice`, fallback `priceFormatted`).
    - `category`: catégorie heuristique basée sur le nom (peut être `autres`).
    - `image_url`: URL d’image (priorité à `productPicture` ou premier lien des renditions).
    - `is_promotion`: booléen, `true` si présent dans l’index `offers`.
    - `promo_text`: texte promo/description, parfois HTML.
    - `valid_until`: date de fin si disponible, souvent `null` (peu exposée par Algolia).
    - `unit`: unité affichée (ex. `salesUnitFormatted`, `salesUnit2`).
- `data/metadata.json`: résumé minimal (`schema_version`, `last_updated`, `total_products`).

## Contrôles rapides
- Compter les produits: `jq '.products | length' data/products-min.json`
- Compter les promotions: `jq '[.products[] | select(.is_promotion)] | length' data/products-min.json`
- Vérifier les champs manquants: `grep -c '"price": null' data/products-min.json` etc.

## Optimisations de pagination

Le scraper utilise une pagination optimisée avec les caractéristiques suivantes:

- **Délais entre requêtes**: 300-900ms aléatoires pour simuler un comportement humain et éviter le rate-limiting
- **Logging progressif**: affichage du numéro de page, hits par page, et total cumulé
- **Gestion d'erreurs robuste**: retour des résultats partiels en cas d'erreur, plutôt qu'échec total
- **Limite de sécurité**: maximum 100 pages pour prévenir les boucles infinies

**Limitation importante**: L'API de recherche Algolia a une limite stricte de **1000 résultats maximum** par requête, même avec pagination. Pour dépasser cette limite, il faudrait soit:
- Utiliser l'API Browse (nécessite des permissions différentes)
- Effectuer plusieurs requêtes filtrées (par catégorie, prix, etc.)

Résultats actuels: ~1270 produits (1000 de `assortment` + ~270 de `offers`)

## Interprétation et limites
- `price`: certains articles n’ont pas de prix dans la source, `null` est normal.
- `valid_until`: la date de fin de promotion n’est pas toujours fournie dans les hits; peut rester `null`.
- `category`: basée sur des mots-clés; pour une catégorisation précise, mappez `hierarchicalCategories.lvl3/lvl4` vers vos catégories.
- `promo_text`: peut contenir des balises HTML; rendez-le texte selon vos besoins.

## Dépannage
- Erreur `403 Forbidden`:
  - Vérifiez que `ALGOLIA_API_KEY` est une clé “search-only” autorisée pour l’`ALGOLIA_APP_ID` et les indices.
  - Le scraper ajoute `Origin`, `Referer`, `User-Agent` et `x-algolia-agent` pour mimer un navigateur.
  - Test rapide via `curl`:
    - `curl -s -i -X POST "https://W297XVTVRZ-dsn.algolia.net/1/indexes/*/queries" \
      -H "X-Algolia-Application-Id: W297XVTVRZ" \
      -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" \
      -H "Origin: https://www.aldi.be" -H "Referer: https://www.aldi.be/" \
      -H "User-Agent: Mozilla/5.0" \
      --data '{"requests":[{"indexName":"prod_be_fr_assortment","params":"hitsPerPage=1&page=0"}]}'`
- Erreur `Missing ALGOLIA_API_KEY environment variable.`: exportez correctement la clé avant de lancer.
- Mock pour diagnostic: `python3 -m scripts.scraper --dump-mock` (affiche un exemple de réponse Algolia).

## CI/CD
- Workflow: `.github/workflows/scrape-aldi.yml` (exécution hebdomadaire ou déclenchement manuel).
- Secrets requis: `ALGOLIA_API_KEY`.
- Les artefacts générés (fichiers `data/`) sont commités automatiquement si le contenu a changé.

## GitHub Pages
- Activer Pages: `Settings → Pages → Build and deployment → Deploy from a branch`.
- Sélectionner `Branch: main` et `Folder: /(root)`.
- L’URL sera `https://<username>.github.io/<repo>/`.
- Vérifier vos JSON: `https://<username>.github.io/<repo>/data/products.json`.

## Déclenchement manuel (Actions)
- Aller dans `Actions → 🛒 Scrape ALDI Products`.
- Cliquer `Run workflow` pour lancer le scraping et la publication.

## Publier en une commande (local)
- Rendre le script exécutable: `chmod +x scripts/publish.sh`
- Lancer: `./scripts/publish.sh`
- Le script:
  - Exécute le scraper localement.
  - Commit et push les fichiers `data/*.json` si changements.
  - Nécessite que `origin` pointe vers `https://github.com/<username>/<repo>.git` et que vous soyez authentifié.

### Authentification Git la plus simple
- Option recommandée: GitHub CLI
  - Installer: `brew install gh`
  - Se connecter: `gh auth login` (choisir GitHub.com, HTTPS, ouvrir le navigateur pour autoriser).
- Alternative: PAT (token personnel) pour `git push` HTTPS.

## Re-générer le minimal sans re-scraper
- Si `data/products.json` existe déjà, vous pouvez régénérer `products-min.json` en relançant le scraper ou en exécutant un petit script utilisant `AldiScraper().build_min(...)` sur les produits fusionnés.

## Personnalisation
- Ajuster `HITS_PER_PAGE` pour gérer le volume par page.
- Améliorer la catégorisation en mappant `hierarchicalCategories` vers un ensemble de catégories métier.