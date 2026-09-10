import os
import re
import datetime
import sqlite3
import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd

DB_NAME = "brvm.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def telecharger_boc_pdf():
    """Télécharge le bulletin officiel PDF du jour depuis la BRVM."""
    url_page = "https://www.brvm.org/fr/bulletins-officiels-de-la-cote"
    
    try:
        res = requests.get(url_page, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.content, "html.parser")
        
        pdf_url = None
        # Recherche du premier lien PDF correspondant au BOC du jour
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower() and ("boc" in a["href"].lower() or "bulletin" in a["href"].lower()):
                pdf_url = a["href"]
                break
                
        if not pdf_url:
            # Repli sur le format d'URL directe standard par date
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            pdf_url = f"https://www.brvm.org/sites/default/files/boc_{today_str}.pdf"
        elif not pdf_url.startswith("http"):
            pdf_url = "https://www.brvm.org" + pdf_url

        print(f"Téléchargement du BOC : {pdf_url}")
        pdf_res = requests.get(pdf_url, headers=HEADERS, timeout=30)
        
        if pdf_res.status_code == 200:
            file_path = "boc_temp.pdf"
            with open(file_path, "wb") as f:
                f.write(pdf_res.content)
            return file_path
        else:
            print(f"Échec de téléchargement du PDF (Code HTTP: {pdf_res.status_code})")
    except Exception as e:
        print(f"Erreur lors du téléchargement du BOC : {e}")
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
                    # Nettoyage des cellules
                    ligne_propre = [str(cell).strip().replace("\n", " ") if cell else "" for cell in ligne]
                    
                    # Détection des lignes d'actions (Ticker de 3 à 8 caractères majuscules en colonne 0 ou 1)
                    if len(ligne_propre) >= 5:
                        ticker = ligne_propre[0].upper()
                        
                        # Vérification de format Ticker (ex: SNTS, ETIT, ORGT)
                        if re.match(r"^[A-Z0-9]{3,8}$", ticker) and ticker not in ["SYMBOLE", "TITRE", "CODE"]:
                            try:
                                # Extraction et nettoyage numérique des données
                                cours = float(ligne_propre[3].replace(" ", "").replace(",", "."))
                                var_raw = ligne_propre[4].replace(" ", "").replace(",", ".").replace("%", "")
                                variation = float(var_raw) if var_raw else 0.0
                                
                                # Volume transigé si présent
                                volume = 0
                                if len(ligne_propre) > 5 and ligne_propre[5].replace(" ", "").isdigit():
                                    volume = int(ligne_propre[5].replace(" ", ""))

                                donnees.append({
                                    "Ticker": ticker,
                                    "Cours (FCFA)": cours,
                                    "Variation (%)": variation,
                                    "Volume": volume,
                                    "Date": date_du_jour
                                })
                            except (ValueError, IndexError):
                                continue

    return pd.DataFrame(donnees)

def mettre_a_jour_base_sqlite(df):
    """Enregistre les données extraites dans la base SQLite."""
    if df.empty:
        print("Aucune donnée valide n'a été extraite du PDF.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Création des tables si inexistantes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening (
            Ticker TEXT PRIMARY KEY,
            `Cours (FCFA)` REAL,
            `Variation (%)` REAL,
            Volume INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            date TEXT,
            ticker TEXT,
            cours REAL,
            variation REAL,
            volume INTEGER,
            PRIMARY KEY (date, ticker)
        )
    """)

    # 1. Mise à jour de la table screening (vue temps réel / clôture du jour)
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO screening (Ticker, `Cours (FCFA)`, `Variation (%)`, Volume)
            VALUES (?, ?, ?, ?)
        """, (row["Ticker"], row["Cours (FCFA)"], row["Variation (%)"], row["Volume"]))

    # 2. Insertion dans l'historique
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO historique (date, ticker, cours, variation, volume)
            VALUES (?, ?, ?, ?, ?)
        """, (row["Date"], row["Ticker"], row["Cours (FCFA)"], row["Variation (%)"], row["Volume"]))

    conn.commit()
    conn.close()
    print(f"Base SQLite 'brvm.db' mise à jour avec succès ({len(df)} actions enregistrées).")

if __name__ == "__main__":
    fichier_pdf = telecharger_boc_pdf()
    if fichier_pdf:
        df_actions = extraire_donnees_boc(fichier_pdf)
        mettre_a_jour_base_sqlite(df_actions)
        
        # Nettoyage du fichier temporaire
        if os.path.exists(fichier_pdf):
            os.remove(fichier_pdf)