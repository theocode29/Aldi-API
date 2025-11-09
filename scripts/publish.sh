#!/usr/bin/env bash
set -euo pipefail

# Publier en une commande:
# 1) Exécute le scraper
# 2) Commit et push les fichiers générés s'il y a des changements

# Vérifier que git est initialisé et que le remote origin existe
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo "⚠️ Ce dossier n'est pas un dépôt git. Initialisez-le : git init"
  exit 1
fi

if ! git remote get-url origin > /dev/null 2>&1; then
  echo "⚠️ Remote 'origin' absent. Ajoutez-le :"
  echo "   git remote add origin https://github.com/theocode29/Aldi-API"
  exit 1
fi

echo "🚀 Exécution du scraper..."
python3 -m scripts.scraper

echo "🧾 Préparation du commit..."
git add data/metadata.json data/products.json data/products-min.json || true

if git diff --cached --quiet; then
  echo "ℹ️ Aucun changement à publier."
  exit 0
fi

commit_msg="data: update $(date -u +%FT%TZ)"
echo "📝 Commit: $commit_msg"
git commit -m "$commit_msg"

echo "⬆️ Push vers origin/main..."
git push origin main

echo "✅ Publication terminée. Vérifiez GitHub Pages après déploiement."