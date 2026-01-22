import requests
import os
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from datetime import datetime, timezone
from pymongo.errors import BulkWriteError # pas encore utilisé
import psycopg2
from psycopg2.extras import execute_batch


load_dotenv()

# On récupère les id
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

BASE_URL = "https://bsky.social/xrpc"

def create_session():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        raise EnvironmentError(
        "Variables BLUESKY_HANDLE ou BLUESKY_PASSWORD manquantes")

    url = f"{BASE_URL}/com.atproto.server.createSession"
    payload = {
        "identifier": BLUESKY_HANDLE,
        "password": BLUESKY_PASSWORD
    }
    
    # Gestion d'erreurs
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Erreur authentification Bluesky : {e}")

def search_posts(query="fake news", limit=50, max_pages=3):
    all_posts = []
    cursor = None
    # Pagination pour avoir le plus de post possible (pas que les récents) et max_pages pour empêcher les abus (Green IT)
    for _ in range(max_pages):
        params = {
            "q": query,
            "limit": limit,
            "cursor": cursor
        }

        response = requests.get(
            f"{BASE_URL}/app.bsky.feed.searchPosts",
            headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        posts = data.get("posts", [])
        all_posts.extend(posts)

        cursor = data.get("cursor")
        if not cursor:
            break

    return all_posts

def filter_language(posts, allowed=("fr", "en")):
    filtered = []
    ingested_at = datetime.now(timezone.utc)

    for post in posts:
        text = post["record"].get("text", "")
        try:
            lang = detect(text)
            if lang in allowed:
                filtered.append({
                    "uri": post["uri"],
                    "cid": post["cid"],
                    "author": post["author"]["handle"],
                    "text": text,
                    "lang": lang,
                    "created_at": post["record"]["createdAt"], 
                    "ingested_at": ingested_at,                
                    "like_count": post.get("likeCount", 0),
                    "repost_count": post.get("repostCount", 0),
                    "reply_count": post.get("replyCount", 0),
                    "source": "bluesky",
                })
        except LangDetectException:
            continue

    return filtered

def store_posts(posts, conn):
    if not posts:
        return

    query = """
        INSERT INTO raw_posts (
            uri, cid, author, text, lang,
            created_at, ingested_at,
            like_count, repost_count, reply_count,
            source
        )
        VALUES (
            %(uri)s, %(cid)s, %(author)s, %(text)s, %(lang)s,
            %(created_at)s, %(ingested_at)s,
            %(like_count)s, %(repost_count)s, %(reply_count)s,
            %(source)s
        )
        ON CONFLICT (uri) DO NOTHING;
    """

    with conn.cursor() as cursor:
        execute_batch(cursor, query, posts)
        conn.commit()

    print(f"{len(posts)} posts traités (doublons ignorés)")

def init_bluesky_session():
    session = create_session()
    return session["accessJwt"]

def init_postgres():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="fake_news_project",
        user="postgres",
        password="16122003"
    )
    return conn



def run_pipeline(conn):
    raw_posts = search_posts(
        query="fake news",
        limit=50,
        max_pages=3
    )

    clean_posts = filter_language(raw_posts)
    store_posts(clean_posts, conn)

    print("Pipeline terminé avec succès")

if __name__ == "__main__":
    ACCESS_TOKEN = init_bluesky_session()
    conn = init_postgres()
    run_pipeline(conn)
    conn.close()
