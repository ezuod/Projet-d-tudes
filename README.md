# Projet Thumalien — Détection de Fake News sur Bluesky

Pipeline d'analyse NLP pour détecter les fake news sur Bluesky, évaluer leur impact émotionnel et fournir un dashboard de visualisation.

## Architecture

```
src/
├── collect.py       # Collecte des posts Bluesky (API + filtrage FR/EN)
├── preprocess.py    # Nettoyage, tokenisation, embeddings
├── classify.py      # Classification fake news (score de crédibilité)
├── emotions.py      # Analyse émotionnelle
└── db.py            # Connexion PostgreSQL partagée
dashboard/
└── app.py           # Dashboard Streamlit
sql/
└── init.sql         # Schéma de la base de données
```

## Prérequis

- Python 3.10+
- Docker & Docker Compose

## Installation

1. Cloner le repo et créer le fichier `.env` :

```bash
cp .env.example .env
# Remplir les variables BLUESKY_HANDLE, BLUESKY_PASSWORD, POSTGRES_USER, POSTGRES_PASSWORD
```

2. Lancer PostgreSQL :

```bash
docker compose up -d
```

3. Installer les dépendances :

```bash
pip install -r requirements.txt
```

4. Lancer la collecte :

```bash
cd src
python collect.py
```

## Stack technique

| Brique | Outil |
|---|---|
| Collecte | API Bluesky, requests |
| Stockage | PostgreSQL 16 + pgvector |
| NLP | spaCy, Transformers |
| Classification | BERT/RoBERTa |
| Émotions | VADER, Transformers |
| Dashboard | Streamlit |
| Green IT | CodeCarbon |
| Infra | Docker |
