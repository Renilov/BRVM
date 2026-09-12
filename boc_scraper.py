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

OFFICIAL_BRVM_TICKERS = {
    "ABJC", "BICB", "BICC", "BNBC", "BOAB", "BOAC", "BOAM", "BOAN", "BOAS",
    "CABC", "CFAC", "CIEC", "ECOC", "ETIT", "FTSC", "LNBB", "NEIC", "NSBC",
    "NTLC", "ORAC", "ORGT", "PALC", "PRSC", "SAFC", "SCRC", "SDCC", "SDSC",
    "SEMC", "SGBC", "SHEC", "SIBC", "SICC", "SIVC", "SLBC", "SMBC", "SNTS",
    "SOGC", "SPHC", "STAC", "STBC", "TTLC", "TTLS", "UNLC", "UNXC"
}


def parse_float(val):
    if not val:
        return 0.0
    val_clean = str(val).replace(",", ".").replace("%", "").strip()
    cleaned = re.sub(r"[^\d.-]", "", val_clean)
    if cleaned in ("", "-", ".", "-."):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_int(val):
    if not val:
        return 0
    cleaned = re.sub(r"[^\d]", "", str(val))
    return int(cleaned) if cleaned else 0


def convertir_cours(val_str, ticker=""):
    val = parse_float(val_str)
    if val <= 0:
        return 0

    if ticker.upper() != "ETIT" and val < 500:
        val *= 1000.0

    return int(round(val))


def telecharger_boc_pdf():
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
    donnees = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").upper()
            if "MARCHE DES OBLIGATIONS" in text or "CAPITALISATION SECTORIELLE" in text:
                continue

            tableaux = page.extract_tables()
            for tableau in tableaux:
                for ligne in tableau:
                    if not ligne:
                        continue
                    ligne_propre = [str(cell).strip().replace("\n", " ") if cell else "" for cell in ligne]
                    if len(ligne_propre) >= 4:
                        ticker = ligne_propre[0].upper().strip()

                        if ticker in OFFICIAL_BRVM_TICKERS:
                            cours = convertir_cours(ligne_propre[3], ticker)
                            var_raw = ligne_propre[4] if len(ligne_propre) > 4 else "0"
                            variation = parse_float(var_raw)
                            vol_raw = ligne_propre[5] if len(ligne_propre) > 5 else "0"
                            volume = parse_int(vol_raw)

                            # Extraction PER si disponible dans le PDF
                            per_val = "à déterminer"
                            if len(ligne_propre) > 7:
                                float_per = parse_float(ligne_propre[7])
                                if float_per > 0:
                                    per_val = str(float_per)

                            if 0 < cours < 75000:
                                donnees.append({
                                    "Ticker": ticker,
                                    "Nom": ticker,
                                    "Cours (FCFA)": cours,
                                    "Variation (%)": variation,
                                    "Volume": volume,
                                    "PER": per_val,
                                    "Dividende": "à déterminer",
                                    "Date de détachement": "à déterminer",
                                    "Date de paiement": "à déterminer",
                                    "date_maj": date_maj,
                                })

    df = pd.DataFrame(donnees)
    if not df.empty:
        df = df.drop_duplicates(subset=["Ticker"], keep="first")
    return df


def reinitialiser_et_mettre_a_jour_sqlite(df):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS screening")
    cursor.execute("""
        CREATE TABLE screening (
            Ticker TEXT PRIMARY KEY,
            Nom TEXT,
            "Cours (FCFA)" INTEGER,
            "Variation (%)" REAL,
            Volume INTEGER,
            PER TEXT,
            Dividende TEXT,
            "Date de détachement" TEXT,
            "Date de paiement" TEXT,
            date_maj TEXT
        )
    """)

    if df.empty:
        print("⚠️ Aucune action valide extraite.")
        conn.commit()
        conn.close()
        return

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO screening (
                Ticker, Nom, "Cours (FCFA)", "Variation (%)", Volume, 
                PER, Dividende, "Date de détachement", "Date de paiement", date_maj
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["Ticker"], row["Nom"], int(row["Cours (FCFA)"]), row["Variation (%)"], row["Volume"],
            row["PER"], row["Dividende"], row["Date de détachement"], row["Date de paiement"], row["date_maj"]
        ))

    conn.commit()
    conn.close()
    print(f"✅ Base 'brvm.db' mise à jour avec {len(df)} actions et nouvelles colonnes.")


if __name__ == "__main__":
    fichier_pdf, date_boc = telecharger_boc_pdf()
    if fichier_pdf and date_boc:
        df_actions = extraire_donnees_boc(fichier_pdf, date_boc)
        reinitialiser_et_mettre_a_jour_sqlite(df_actions)

        if os.path.exists(fichier_pdf):
            os.remove(fichier_pdf)