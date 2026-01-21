import requests
import os
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from pymongo import MongoClient
from datetime import datetime, timezone
from pymongo.errors import BulkWriteError


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


def store_posts(posts, collection):
    if not posts:
        return

    try:
        result = collection.insert_many(posts, ordered=False)
        print(f"{len(result.inserted_ids)} posts insérés")

    except BulkWriteError as e:
        inserted = e.details.get("nInserted", 0)
        print(f"{inserted} posts insérés, doublons ignorés")


def init_bluesky_session():
    session = create_session()
    return session["accessJwt"]

def init_mongodb():
    client = MongoClient("mongodb://localhost:27017")
    db = client["fake_news_project"]
    collection = db["raw_posts"]

    # Index unique pour éviter les doublons
    collection.create_index("uri", unique=True)

    return collection


def run_pipeline(collection):
    raw_posts = search_posts(
        query="fake news",
        limit=50,
        max_pages=3
    )

    clean_posts = filter_language(raw_posts)

    store_posts(clean_posts, collection)

    print("Pipeline terminée avec succès")

if __name__ == "__main__":
    # Authentification Bluesky
    ACCESS_TOKEN = init_bluesky_session()

    # Connexion MongoDB
    collection = init_mongodb()

    # Lancement pipeline
    run_pipeline(collection)
