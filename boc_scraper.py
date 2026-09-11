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
    """Télécharge le BOC du jour ou recherche le plus récent des 7 derniers jours."""
    url_page = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
    today = datetime.date.today()

    # 1. Recherche du bulletin sur le site officiel
    try:
        res = requests.get(url_page, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = bs4.BeautifulSoup(res.content, "html.parser")
            for a in soup.find_all("a", href=True):
                if ".pdf" in a["href"].lower() and ("boc" in a["href"].lower() or "bulletin" in a["href"].lower()):
                    pdf_url = a["href"] if a["href"].startswith("http") else "https://www.brvm.org" + a["href"]
                    pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=20)
                    if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                        file_path = "boc_temp.pdf"
                        with open(file_path, "wb") as f:
                            f.write(pdf_res.content)
                        date_str = today.strftime("%Y-%m-%d")
                        print(f"🎯 Bulletin du jour trouvé ({date_str})")
                        return file_path, date_str
    except Exception as e:
        print(f"⚠️ Erreur lors de la recherche sur la page BRVM : {e}")

    # 2. Repli : Recherche rétrospective jusqu'à 7 jours en arrière
    print("🔄 Recherche des bulletins des jours précédents...")
    for i in range(1, 8):
        date_cible = today - datetime.timedelta(days=i)
        date_str_file = date_cible.strftime("%Y%m%d")
        date_str_iso = date_cible.strftime("%Y-%m-%d")

        urls_a_tester = [
            f"https://www.brvm.org/sites/default/files/boc_{date_str_file}.pdf",
            f"https://www.brvm.org/sites/default/files/boc_{date_str_file}_1.pdf",
            f"https://www.brvm.org/sites/default/files/boc_{date_str_file}_2.pdf",
        ]

        for pdf_url in urls_a_tester:
            try:
                pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=5)
                if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                    print(f"📌 BOC le plus récent trouvé : Date du {date_cible.strftime('%d/%m/%Y')}")
                    file_path = "boc_temp.pdf"
                    with open(file_path, "wb") as f:
                        f.write(pdf_res.content)
                    return file_path, date_str_iso
            except Exception:
                continue

    print("❌ Aucun bulletin officiel trouvé sur les 7 derniers jours.")
    return None, None


def extraire_donnees_boc(pdf_path, date_maj):
    """Parse le PDF et attribue la date exacte du BOC récupéré."""
    donnees = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tableaux = page.extract_tables()
            for tableau in tableaux:
                for ligne in tableau:
                    if not ligne:
                        continue
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
                                    "Nom": ticker,
                                    "Cours (FCFA)": cours,
                                    "Variation (%)": variation,
                                    "Volume": volume,
                                    "date_maj": date_maj,
                                })
                            except (ValueError, IndexError):
                                continue

    return pd.DataFrame(donnees)


def mettre_a_jour_base_sqlite(df):
    """Enregistre les données extraites dans SQLite."""
    if df.empty:
        print("⚠️ Aucune donnée à enregistrer.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

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

    date_boc = df["date_maj"].iloc[0]

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO screening (Ticker, Nom, "Cours (FCFA)", "Variation (%)", Volume, date_maj)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (row["Ticker"], row["Nom"], row["Cours (FCFA)"], row["Variation (%)"], row["Volume"], row["date_maj"]))

        cursor.execute("""
            INSERT INTO historique (ticker, date, cours, volume)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                cours = excluded.cours,
                volume = excluded.volume
        """, (row["Ticker"], row["date_maj"], row["Cours (FCFA)"], row["Volume"]))

    conn.commit()
    conn.close()
    print(f"✅ Base SQLite 'brvm.db' mise à jour avec succès.")
    print(f"📅 Date du BOC enregistré : {date_boc}")


if __name__ == "__main__":
    fichier_pdf, date_boc = telecharger_boc_pdf()
    if fichier_pdf and date_boc:
        df_actions = extraire_donnees_boc(fichier_pdf, date_boc)
        mettre_a_jour_base_sqlite(df_actions)

        if os.path.exists(fichier_pdf):
            os.remove(fichier_pdf)