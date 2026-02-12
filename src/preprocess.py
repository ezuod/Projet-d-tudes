"""Prétraitement des datasets Kaggle pour fine-tuning RoBERTa."""

import os
import re
import zipfile
from datetime import datetime

import pandas as pd
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

MIN_TEXT_LENGTH = 100
RANDOM_STATE = 42

report_lines = []


def log(msg):
    print(msg)
    report_lines.append(msg)


def load_dataset_1():
    """#1 ISOT — Real & Fake news (Fake.csv + True.csv, 44k articles)."""
    path = os.path.join(RAW_DIR, "Real & Fake news.zip")
    with zipfile.ZipFile(path) as z:
        fake = pd.read_csv(z.open("Fake.csv"))
        fake["label"] = 0
        real = pd.read_csv(z.open("True.csv"))
        real["label"] = 1
    df = pd.concat([fake, real], ignore_index=True)
    df["text"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
    return df[["text", "label"]]


def load_dataset_2():
    """#2 Mehul — Fake & Real News (fakenrealnews.csv)."""
    path = os.path.join(RAW_DIR, "Fake & Real News.zip")
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(z.open("fakenrealnews.csv"))
    df["label"] = df["label"].map({"FAKE": 0, "REAL": 1})
    df["text"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
    return df[["text", "label"]]


def load_dataset_5():
    """#5 Ronik — Fake News (fake_news.csv, 20k, labels inversés)."""
    path = os.path.join(RAW_DIR, "Fake News.zip")
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(z.open("fake_news.csv"))
    df["label"] = df["label"].map({1: 0, 0: 1})
    df["text"] = (df["title"].fillna("") + " " + df["text"].fillna("")).str.strip()
    return df[["text", "label"]]


def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"pic\.twitter\.com/\S+", "", text)
    text = re.sub(r"t\.co/\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[iframe[^\]]*\]", "", text)
    text = re.sub(r"Reporting by .+?(?:Editing by .+?)?(?:\n|$)", "", text)
    text = re.sub(r"FILE PHOTO:?\s*", "", text)
    text = re.sub(r"REUTERS/\S+", "", text)
    text = re.sub(r"Share this article.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Featured image via.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Google Pinterest Digg Linkedin Reddit Stumbleupon Print Delicious Pocket Tumblr\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_preprocessing():
    os.makedirs(DATA_DIR, exist_ok=True)
    log(f"=== Preprocessing demarre : {datetime.now().isoformat()} ===")
    log("")

    log("--- Etape 0 : Chargement des datasets ---")
    df1 = load_dataset_1()
    log(f"#1 ISOT : {len(df1)} articles (fake={(df1['label']==0).sum()}, real={(df1['label']==1).sum()})")
    df2 = load_dataset_2()
    log(f"#2 Mehul : {len(df2)} articles (fake={(df2['label']==0).sum()}, real={(df2['label']==1).sum()})")
    df5 = load_dataset_5()
    log(f"#5 Ronik : {len(df5)} articles (fake={(df5['label']==0).sum()}, real={(df5['label']==1).sum()})")
    log("#3 Sahide : EXCLU (synthetique, 1k lignes, bilingue EN/TR)")
    log("#4 Vishal : EXCLU (doublon du #1)")
    log("")

    log("--- Etape 1 : Merge ---")
    df = pd.concat([df1, df2, df5], ignore_index=True)
    log(f"Total apres merge : {len(df)} articles")
    log(f"  Fake : {(df['label']==0).sum()}")
    log(f"  Real : {(df['label']==1).sum()}")
    log("")

    log("--- Etape 2 : Suppression des nulls ---")
    before = len(df)
    df = df.dropna(subset=["text"])
    df = df[df["text"].str.strip() != ""]
    removed = before - len(df)
    log(f"{removed} lignes null/vides supprimees")
    log(f"Restant : {len(df)}")
    log("")

    log("--- Etape 3 : Suppression des labels contradictoires ---")
    before = len(df)
    label_counts = df.groupby("text")["label"].nunique()
    conflicting_texts = label_counts[label_counts > 1].index
    df = df[~df["text"].isin(conflicting_texts)]
    removed = before - len(df)
    log(f"{removed} lignes avec labels contradictoires supprimees ({len(conflicting_texts)} textes uniques)")
    log(f"Restant : {len(df)}")
    log("")

    log("--- Etape 4 : Deduplication ---")
    before = len(df)
    df = df.drop_duplicates(subset=["text"], keep="first")
    removed = before - len(df)
    log(f"{removed} doublons supprimes")
    log(f"Restant : {len(df)}")
    log("")

    log("--- Etape 5 : Suppression des textes < 100 chars ---")
    before = len(df)
    df = df[df["text"].str.len() >= MIN_TEXT_LENGTH]
    removed = before - len(df)
    log(f"{removed} textes courts supprimes")
    log(f"Restant : {len(df)}")
    log("")

    log("--- Etape 6 : Nettoyage du texte ---")
    df["text"] = df["text"].apply(clean_text)
    log("Nettoyage applique (URLs, HTML, Reuters, boilerplate...)")
    log("")

    log("--- Etape 7 : Re-filtrage post-nettoyage ---")
    before = len(df)
    df = df[df["text"].str.len() >= MIN_TEXT_LENGTH]
    df = df[df["text"].str.strip() != ""]
    removed = before - len(df)
    log(f"{removed} textes devenus trop courts apres nettoyage")
    log(f"Restant : {len(df)}")
    log("")

    log("--- Etape 8 : Verification de l'equilibre ---")
    fake_count = (df["label"] == 0).sum()
    real_count = (df["label"] == 1).sum()
    total = len(df)
    fake_pct = fake_count / total * 100
    real_pct = real_count / total * 100
    log(f"Fake : {fake_count} ({fake_pct:.1f}%)")
    log(f"Real : {real_count} ({real_pct:.1f}%)")
    if max(fake_pct, real_pct) > 60:
        log("WARNING : desequilibre > 60/40 !")
    else:
        log("OK : equilibre acceptable")
    log("")

    log("--- Etape 9 : Export dataset nettoye ---")
    df = df.reset_index(drop=True)
    clean_path = os.path.join(DATA_DIR, "dataset_clean.csv")
    df.to_csv(clean_path, index=False)
    log(f"Dataset nettoye : {clean_path} ({len(df)} lignes)")
    log("")

    log("--- Etape 10 : Split train/val/test (80/10/10) ---")
    train_df, temp_df = train_test_split(df, test_size=0.2, random_state=RANDOM_STATE, stratify=df["label"])
    val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=RANDOM_STATE, stratify=temp_df["label"])

    train_df.to_csv(os.path.join(DATA_DIR, "train.csv"), index=False)
    val_df.to_csv(os.path.join(DATA_DIR, "val.csv"), index=False)
    test_df.to_csv(os.path.join(DATA_DIR, "test.csv"), index=False)

    for name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        f = (split_df["label"] == 0).sum()
        r = (split_df["label"] == 1).sum()
        log(f"{name} : {len(split_df)} lignes (fake={f}, real={r})")

    log("")
    log(f"=== Preprocessing termine : {datetime.now().isoformat()} ===")

    report_path = os.path.join(DATA_DIR, "cleaning_report.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"\nRapport sauvegarde : {report_path}")


if __name__ == "__main__":
    run_preprocessing()
