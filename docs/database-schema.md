# Architecture Base de Données — Projet Thumalien

## Vue d'ensemble

PostgreSQL 16 + pgvector. 6 tables, 1 vue, séparées par étape du pipeline.

```
API Bluesky
    │
    ▼
┌──────────────┐
│  raw_posts   │  Données brutes collectées
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ processed_posts  │  Textes nettoyés + embeddings vectoriels (384d)
└──────┬───────────┘
       │
       ├────────────────────────┐
       ▼                        ▼
┌─────────────────┐   ┌───────────────┐
│ classifications │   │   emotions    │
│ fake/legit +    │   │ colère, peur, │
│ score confiance │   │ joie...       │
└─────────────────┘   └───────────────┘
       │                        │
       └────────┬───────────────┘
                ▼
     ┌─────────────────────┐
     │  v_posts_dashboard  │  Vue combinée → Streamlit
     └─────────────────────┘

┌─────────────────┐     ┌───────────────┐
│ pipeline_runs   │◄────│ energy_logs   │
│ traçabilité     │     │ Green IT      │
└─────────────────┘     └───────────────┘
```

---

## Tables

### `pipeline_runs` — Journal de bord du pipeline

Chaque exécution d'une étape (collecte, prétraitement, classification, émotions) crée une entrée.

| Colonne | Type | Description |
|---|---|---|
| id | SERIAL PK | Identifiant auto-incrémenté |
| step | VARCHAR(50) | Étape : 'collect', 'preprocess', 'classify', 'emotions' |
| started_at | TIMESTAMPTZ | Début d'exécution |
| finished_at | TIMESTAMPTZ | Fin d'exécution (NULL si en cours) |
| status | VARCHAR(20) | 'running', 'success' ou 'failed' |
| posts_processed | INTEGER | Nombre de posts traités |
| details | JSONB | Détails libres (paramètres, erreurs...) |

---

### `raw_posts` — Posts bruts Bluesky

Table d'entrée du pipeline. Données jamais modifiées après insertion.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| uri | TEXT | PK | Identifiant unique Bluesky |
| cid | TEXT | NOT NULL | Content ID Bluesky |
| author | TEXT | NOT NULL | Handle de l'auteur |
| text | TEXT | NOT NULL | Texte du post |
| lang | VARCHAR(5) | CHECK ('fr','en') | Langue détectée |
| created_at | TIMESTAMPTZ | NOT NULL | Date de publication |
| ingested_at | TIMESTAMPTZ | DEFAULT NOW() | Date de collecte |
| like_count | INTEGER | >= 0, DEFAULT 0 | Nombre de likes |
| repost_count | INTEGER | >= 0, DEFAULT 0 | Nombre de reposts |
| reply_count | INTEGER | >= 0, DEFAULT 0 | Nombre de réponses |
| source | VARCHAR(50) | DEFAULT 'bluesky' | Plateforme source |

**Index** : lang, created_at, author

---

### `processed_posts` — Textes nettoyés + embeddings

Résultat du prétraitement NLP. Relation 1:1 avec raw_posts.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| uri | TEXT | PK, FK → raw_posts | Lien vers le post brut |
| clean_text | TEXT | NOT NULL | Texte nettoyé (sans URLs, mentions, etc.) |
| embedding | vector(384) | — | Vecteur sémantique (sentence-transformers) |
| token_count | INTEGER | >= 0 | Nombre de tokens |
| processed_at | TIMESTAMPTZ | DEFAULT NOW() | Date de traitement |

**Index** : HNSW sur embedding (cosine) pour recherche de similarité

---

### `classifications` — Détection fake news

Résultat de la classification. Relation 1:1 avec raw_posts.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| uri | TEXT | PK, FK → raw_posts | Lien vers le post brut |
| label | VARCHAR(20) | CHECK ('fake','legit','unverified') | Résultat |
| confidence_score | FLOAT | CHECK [0, 1] | Score de confiance du modèle |
| explanation | TEXT | — | Pourquoi ce label (explicabilité IA) |
| model_name | VARCHAR(100) | NOT NULL | Modèle utilisé |
| classified_at | TIMESTAMPTZ | DEFAULT NOW() | Date de classification |

**Index** : label, confidence_score

---

### `emotions` — Analyse émotionnelle

Plusieurs émotions possibles par post. Relation 1:N avec raw_posts.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| id | SERIAL | PK | Identifiant auto-incrémenté |
| uri | TEXT | FK → raw_posts, NOT NULL | Lien vers le post brut |
| emotion | VARCHAR(50) | NOT NULL | Émotion détectée (anger, fear, joy...) |
| score | FLOAT | CHECK [0, 1] | Intensité de l'émotion |
| model_name | VARCHAR(100) | NOT NULL | Modèle utilisé |
| analyzed_at | TIMESTAMPTZ | DEFAULT NOW() | Date d'analyse |

**Contrainte** : UNIQUE (uri, emotion, model_name) — empêche les doublons
**Index** : uri, emotion

---

### `energy_logs` — Suivi Green IT

Mesures de consommation énergétique par exécution (CodeCarbon).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| id | SERIAL | PK | Identifiant auto-incrémenté |
| pipeline_run_id | INTEGER | FK → pipeline_runs | Exécution associée |
| step | VARCHAR(50) | NOT NULL | Étape mesurée |
| duration_seconds | FLOAT | >= 0 | Durée d'exécution |
| energy_kwh | FLOAT | >= 0 | Énergie consommée |
| co2_kg | FLOAT | >= 0 | Émissions CO2 |
| cpu_power_watts | FLOAT | >= 0 | Puissance CPU |
| logged_at | TIMESTAMPTZ | DEFAULT NOW() | Date de mesure |

**Index** : step

---

## Vue

### `v_posts_dashboard` — Vue combinée pour Streamlit

Jointure automatique raw_posts + processed_posts + classifications.
Le dashboard fait un simple `SELECT * FROM v_posts_dashboard` au lieu de jointures manuelles.

Colonnes exposées : uri, author, original_text, lang, created_at, ingested_at, like_count, repost_count, reply_count, clean_text, token_count, label, confidence_score, explanation, classification_model.

Les émotions ne sont pas dans la vue car la relation est 1:N (un post = plusieurs émotions). Elles sont requêtées séparément.

---

## Choix techniques

| Décision | Justification |
|---|---|
| pgvector (HNSW, cosine) | Recherche de posts sémantiquement similaires en millisecondes |
| Tables séparées par étape | Chaque membre travaille sur sa table sans conflit, pipeline rejouable |
| CHECK constraints partout | Aucune donnée incohérente ne peut être insérée |
| CASCADE sur FK | Suppression d'un post brut nettoie automatiquement les résultats |
| UNIQUE (uri, emotion, model_name) | Empêche les doublons si on relance le pipeline |
| JSONB pour details | Flexible pour stocker des paramètres variables par exécution |
| Vue dashboard | Simplifie le code Streamlit, pas de duplication de données |
