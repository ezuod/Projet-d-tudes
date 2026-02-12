-- ============================================================
-- Projet Thumalien - Schéma BDD optimisé
-- PostgreSQL 16 + pgvector
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLES
-- ============================================================

-- Traçabilité des exécutions du pipeline
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    step VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed')),
    posts_processed INTEGER DEFAULT 0,
    details JSONB
);

-- Données brutes collectées depuis Bluesky
CREATE TABLE IF NOT EXISTS raw_posts (
    uri TEXT PRIMARY KEY,
    cid TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    lang VARCHAR(5) NOT NULL
        CHECK (lang IN ('fr', 'en')),
    created_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    like_count INTEGER NOT NULL DEFAULT 0
        CHECK (like_count >= 0),
    repost_count INTEGER NOT NULL DEFAULT 0
        CHECK (repost_count >= 0),
    reply_count INTEGER NOT NULL DEFAULT 0
        CHECK (reply_count >= 0),
    source VARCHAR(50) NOT NULL DEFAULT 'bluesky'
);

-- Textes nettoyés + embeddings vectoriels
CREATE TABLE IF NOT EXISTS processed_posts (
    uri TEXT PRIMARY KEY
        REFERENCES raw_posts(uri) ON DELETE CASCADE,
    clean_text TEXT NOT NULL,
    embedding vector(384),
    token_count INTEGER
        CHECK (token_count >= 0),
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Classification fake news
CREATE TABLE IF NOT EXISTS classifications (
    uri TEXT PRIMARY KEY
        REFERENCES raw_posts(uri) ON DELETE CASCADE,
    label VARCHAR(20) NOT NULL
        CHECK (label IN ('fake', 'legit', 'unverified')),
    confidence_score FLOAT NOT NULL
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    explanation TEXT,
    model_name VARCHAR(100) NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Analyse émotionnelle (plusieurs émotions par post)
CREATE TABLE IF NOT EXISTS emotions (
    id SERIAL PRIMARY KEY,
    uri TEXT NOT NULL
        REFERENCES raw_posts(uri) ON DELETE CASCADE,
    emotion VARCHAR(50) NOT NULL,
    score FLOAT NOT NULL
        CHECK (score >= 0 AND score <= 1),
    model_name VARCHAR(100) NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (uri, emotion, model_name)
);

-- Suivi énergétique Green IT (CodeCarbon)
CREATE TABLE IF NOT EXISTS energy_logs (
    id SERIAL PRIMARY KEY,
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    step VARCHAR(50) NOT NULL,
    duration_seconds FLOAT NOT NULL
        CHECK (duration_seconds >= 0),
    energy_kwh FLOAT
        CHECK (energy_kwh >= 0),
    co2_kg FLOAT
        CHECK (co2_kg >= 0),
    cpu_power_watts FLOAT
        CHECK (cpu_power_watts >= 0),
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEX DE PERFORMANCE
-- ============================================================

-- raw_posts : filtrage dashboard (langue, date, auteur)
CREATE INDEX IF NOT EXISTS idx_raw_posts_lang ON raw_posts(lang);
CREATE INDEX IF NOT EXISTS idx_raw_posts_created_at ON raw_posts(created_at);
CREATE INDEX IF NOT EXISTS idx_raw_posts_author ON raw_posts(author);

-- classifications : filtrage par label et tri par score
CREATE INDEX IF NOT EXISTS idx_classifications_label ON classifications(label);
CREATE INDEX IF NOT EXISTS idx_classifications_confidence ON classifications(confidence_score);

-- emotions : lookup par post et par émotion
CREATE INDEX IF NOT EXISTS idx_emotions_uri ON emotions(uri);
CREATE INDEX IF NOT EXISTS idx_emotions_emotion ON emotions(emotion);

-- energy_logs : filtrage par étape
CREATE INDEX IF NOT EXISTS idx_energy_logs_step ON energy_logs(step);

-- pgvector : recherche de similarité vectorielle (cosine) via HNSW
CREATE INDEX IF NOT EXISTS idx_processed_posts_embedding
    ON processed_posts USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- VUE DASHBOARD (jointure pré-calculée pour Streamlit)
-- ============================================================

CREATE OR REPLACE VIEW v_posts_dashboard AS
SELECT
    r.uri,
    r.author,
    r.text AS original_text,
    r.lang,
    r.created_at,
    r.ingested_at,
    r.like_count,
    r.repost_count,
    r.reply_count,
    p.clean_text,
    p.token_count,
    c.label,
    c.confidence_score,
    c.explanation,
    c.model_name AS classification_model
FROM raw_posts r
LEFT JOIN processed_posts p USING (uri)
LEFT JOIN classifications c USING (uri);
