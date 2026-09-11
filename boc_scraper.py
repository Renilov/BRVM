import datetime
import os
import re
import sqlite3
import bs4
import pandas as pd
import pdfplumber
import requests

DB_NAME = "brvm.db"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def telecharger_boc_pdf():
    """Télécharge le bulletin officiel PDF du jour depuis la BRVM."""
    url_page = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"

    try:
        res = requests.get(url_page, headers=HEADERS, timeout=15)
        soup = bs4.BeautifulSoup(res.content, "html.parser")

        pdf_url = None
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower() and ("boc" in a["href"].lower() or "bulletin" in a["href"].lower()):
                pdf_url = a["href"]
                break

        if not pdf_url:
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            pdf_url = f"https://www.brvm.org/sites/default/files/boc_{today_str}.pdf"
        elif not pdf_url.startswith("http"):
            pdf_url = "https://www.brvm.org" + pdf_url

        print(f"📥 Téléchargement du BOC : {pdf_url}")
        pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=30)

        if pdf_res.status_code == 200:
            file_path = "boc_temp.pdf"
            with open(file_path, "wb") as f:
                f.write(pdf_res.content)
            return file_path
        else:
            print(f"❌ Échec de téléchargement du PDF (Code HTTP: {pdf_res.status_code})")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement du BOC : {e}")
    return None


def extraire_donnees_boc(pdf_path):
    """Parse le PDF du BOC et extrait les tableaux d'actions."""
    donnees = []
    date_du_jour = datetime.datetime.now().strftime("%Y-%m-%d")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tableaux = page.extract_tables()
            for tableau in tableaux:
                for ligne in tableau:
                    ligne_propre = [str(cell).strip().replace("\n", " ") if cell else "" for cell in ligne]

                    if len(ligne_propre) >= 5:
                        ticker = ligne_propre[0].upper()

                        if re.match(r"^[A-Z0-9]{3,8}$", ticker) and ticker not in ["SYMBOLE", "TITRE", "CODE"]:
                            try:
                                cours = float(ligne_propre[3].replace(" ", "").replace(",", "."))
                                var_raw = ligne_propre[4].replace(" ", "").replace(",", ".").replace("%", "")
                                variation = float(var_raw) if var_raw else 0.0

                                volume = 0
                                if len(ligne_propre) > 5 and ligne_propre[5].replace(" ", "").isdigit():
                                    volume = int(ligne_propre[5].replace(" ", ""))

                                donnees.append({
                                    "Ticker": ticker,
                                    "Nom": ticker,  # Nom par défaut identique au Ticker
                                    "Cours (FCFA)": cours,
                                    "Variation (%)": variation,
                                    "Volume": volume,
                                    "date_maj": date_du_jour,
                                })
                            except (ValueError, IndexError):
                                continue

    return pd.DataFrame(donnees)


def mettre_a_jour_base_sqlite(df):
    """Enregistre les données extraites dans la base SQLite."""
    if df.empty:
        print("⚠️ Aucune donnée valide n'a été extraite du PDF.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Alignement des tables sur la structure exacte de app.py
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening (
            Ticker TEXT PRIMARY KEY,
            Nom TEXT,
            "Cours (FCFA)" REAL,
            "Variation (%)" REAL,
            Volume INTEGER,
            date_maj TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date TEXT,
            cours REAL,
            volume INTEGER,
            UNIQUE(ticker, date) ON CONFLICT REPLACE
        )
    """)

    # 1. Mise à jour de la table screening
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO screening (Ticker, Nom, "Cours (FCFA)", "Variation (%)", Volume, date_maj)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row["Ticker"],
            row["Nom"],
            row["Cours (FCFA)"],
            row["Variation (%)"],
            row["Volume"],
            row["date_maj"]
        ))

    # 2. Insertion dans l'historique
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO historique (ticker, date, cours, volume)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                cours = excluded.cours,
                volume = excluded.volume
        """, (
            row["Ticker"],
            row["date_maj"],
            row["Cours (FCFA)"],
            row["Volume"]
        ))

    conn.commit()
    conn.close()
    print(f"✅ Base SQLite 'brvm.db' mise à jour avec succès ({len(df)} actions enregistrées).")


if __name__ == "__main__":
    fichier_pdf = telecharger_boc_pdf()
    if fichier_pdf:
        df_actions = extraire_donnees_boc(fichier_pdf)
        mettre_a_jour_base_sqlite(df_actions)

        if os.path.exists(fichier_pdf):
            os.remove(fichier_pdf)