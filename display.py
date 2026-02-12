import pymongo
import pandas as pd

def export_posts_to_csv():
    # 1. Connexion au serveur local
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    
    # 2. Accès à la base de données et à la collection
    db = client["fake_news_project"]
    collection = db["raw_posts"]
    
    # 3. Récupération de tous les documents
    posts = list(collection.find())
    
    if not posts:
        print("La base est vide. Rien à exporter.")
        return

    # 4. Conversion en DataFrame Pandas (Tableau)
    df = pd.DataFrame(posts)
    
    # Optionnel : Supprimer la colonne '_id' de MongoDB qui n'est pas utile en CSV
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])
    
    # 5. Sauvegarde en CSV
    file_name = "export_bluesky.csv"
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    
    print(f"--- EXPORT RÉUSSI ---")
    print(f"Le fichier '{file_name}' a été créé avec {len(df)} lignes.")
    print(f"Colonnes exportées : {list(df.columns)}")

if __name__ == "__main__":
    export_posts_to_csv()