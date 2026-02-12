import requests
import os
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from datetime import datetime, timezone
from psycopg2.extras import execute_batch
import psycopg2

from db import get_connection

load_dotenv()

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

BASE_URL = "https://bsky.social/xrpc"


def create_session():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        raise EnvironmentError(
            "Variables BLUESKY_HANDLE ou BLUESKY_PASSWORD manquantes"
        )

    url = f"{BASE_URL}/com.atproto.server.createSession"
    payload = {
        "identifier": BLUESKY_HANDLE,
        "password": BLUESKY_PASSWORD,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Erreur authentification Bluesky : {e}")


def search_posts(access_token, query="fake news", limit=50, max_pages=3):
    all_posts = []
    cursor = None
    # Pagination pour avoir le plus de posts possible et max_pages pour limiter les appels (Green IT)
    for _ in range(max_pages):
        params = {
            "q": query,
            "limit": limit,
            "cursor": cursor,
        }

        try:
            response = requests.get(
                f"{BASE_URL}/app.bsky.feed.searchPosts",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la collecte (page ignoree) : {e}")
            break

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
        print("Aucun post a inserer.")
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

    try:
        with conn.cursor() as cur:
            execute_batch(cur, query, posts)
            conn.commit()
        print(f"{len(posts)} posts traites (doublons ignores)")
    except psycopg2.Error as e:
        conn.rollback()
        print(f"Erreur lors de l'insertion en base : {e}")


def init_bluesky_session():
    session = create_session()
    return session["accessJwt"]


def run_pipeline(access_token, conn):
    print("Demarrage de la collecte...")

    raw_posts = search_posts(access_token, query="fake news", limit=50, max_pages=3)
    print(f"{len(raw_posts)} posts bruts collectes")

    clean_posts = filter_language(raw_posts)
    print(f"{len(clean_posts)} posts apres filtrage FR/EN")

    store_posts(clean_posts, conn)
    print("Pipeline termine avec succes")


if __name__ == "__main__":
    token = init_bluesky_session()
    conn = get_connection()
    try:
        run_pipeline(token, conn)
    finally:
        conn.close()
