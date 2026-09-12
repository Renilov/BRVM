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
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Mots-clés à ignorer impérativement
EXCLUDED_KEYWORDS = {
    "VENDREDI", "LUNDI", "MARDI", "MERCREDI", "JEUDI", "SAMEDI", "DIMANCHE",
    "VOLUME", "VALEUR", "NOMBRE", "BASE", "PER", "TAUX", "TOTAL", "TITRE",
    "SYMBOLE", "MARCHE", "COURS", "VARIATION", "SECTEUR", "INDICE", "BRVM",
    "BULLETIN", "OFFICIEL", "COTE", "ERIUM", "PREVIOUS", "DERNIER", "ACTION"
}


def telecharger_boc_pdf():
    """Télécharge le BOC le plus récent disponible."""
    url_page = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
    today = datetime.date.today()

    try:
        res = requests.get(url_page, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = bs4.BeautifulSoup(res.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if ".pdf" in href and ("boc" in href or "bulletin" in href):
                    pdf_url = a["href"] if a["href"].startswith("http") else "https://www.brvm.org" + a["href"]
                    pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=20)
                    if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                        file_path = "boc_temp.pdf"
                        with open(file_path, "wb") as f:
                            f.write(pdf_res.content)
                        return file_path, today.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"⚠️ Erreur de téléchargement direct : {e}")

    for i in range(1, 8):
        date_cible = today - datetime.timedelta(days=i)
        date_str_file = date_cible.strftime("%Y%m%d")
        date_str_iso = date_cible.strftime("%Y-%m-%d")
        for pdf_url in [
            f"https://www.brvm.org/sites/default/files/boc_{date_str_file}.pdf",
            f"https://www.brvm.org/sites/default/files/boc_{date_str_file}_1.pdf",
        ]:
            try:
                pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=5)
                if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                    file_path = "boc_temp.pdf"
                    with open(file_path, "wb") as f:
                        f.write(pdf_res.content)
                    return file_path, date_str_iso
            except Exception:
                continue

    return None, None


def extraire_donnees_boc(pdf_path, date_maj):
    """Extraction filtrée des actions réelles."""
    donnees = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tableaux = page.extract_tables()
            for tableau in tableaux:
                for ligne in tableau:
                    if not ligne:
                        continue
                    ligne_propre = [str(cell).strip().replace("\n", " ") if cell else "" for cell in ligne]
                    if len(ligne_propre) >= 4:
                        ticker = ligne_propre[0].upper().strip()

                        # Validation stricte du ticker
                        if ticker and ticker not in EXCLUDED_KEYWORDS and re.match(r"^[A-Z0-9]{3,8}$", ticker):
                            try:
                                # Nettoyage des chiffres (gestion des séparateurs de milliers)
                                cours_str = ligne_propre[3].replace(" ", "").replace(",", ".")
                                if not cours_str.replace(".", "", 1).isdigit():
                                    continue
                                cours = float(cours_str)

                                var_str = ligne_propre[4].replace(" ", "").replace(",", ".").replace("%", "") if len(ligne_propre) > 4 else "0"
                                variation = float(var_str) if var_str.replace("-", "", 1).replace(".", "", 1).isdigit() else 0.0

                                vol_str = ligne_propre[5].replace(" ", "") if len(ligne_propre) > 5 else "0"
                                volume = int(vol_str) if vol_str.isdigit() else 0

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

    df = pd.DataFrame(donnees).drop_duplicates(subset=["Ticker"])
    return df


def reinitialiser_et_mettre_a_jour_sqlite(df):
    """Purge les fausses données et enregistre les actions réelles."""
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

    # Nettoyage de la table pour éliminer les entêtes parasite enregistrés précédemment
    cursor.execute("DELETE FROM screening")

    if df.empty:
        print("⚠️ Aucune action valide extraite. Vérifiez la structure du PDF.")
        conn.commit()
        conn.close()
        return

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO screening (Ticker, Nom, "Cours (FCFA)", "Variation (%)", Volume, date_maj)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (row["Ticker"], row["Nom"], row["Cours (FCFA)"], row["Variation (%)"], row["Volume"], row["date_maj"]))

    conn.commit()
    conn.close()
    print(f"✅ Base 'brvm.db' nettoyée et mise à jour avec {len(df)} véritables actions.")


if __name__ == "__main__":
    fichier_pdf, date_boc = telecharger_boc_pdf()
    if fichier_pdf and date_boc:
        df_actions = extraire_donnees_boc(fichier_pdf, date_boc)
        reinitialiser_et_mettre_a_jour_sqlite(df_actions)

        if os.path.exists(fichier_pdf):
            os.remove(fichier_pdf)