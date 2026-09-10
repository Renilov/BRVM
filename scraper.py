import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import pandas as pd

# Création automatique du dossier data/ s'il n'existe pas
os.makedirs("data", exist_ok=True)

TICKER_MAP = {
    "AFRICA GLOBAL": "AGLC", "BENIN": "BOAB", "BURKINA": "BOABF", 
    "BANK OF AFRICA CI": "BOAC", "MALI": "BOAM", "NIGER": "BOAN", 
    "SENEGAL": "BOAS", "COMMERCE DU BENIN": "BICB", "BERNABE": "BNBC",
    "BICICI": "BICC", "CFAO": "CFAC", "CIE": "CIEC", "CORIS": "CBIBF", 
    "CROWN": "SEMC", "ECOBANK CI": "ECOC", "ETI": "ETIT", "NEI": "NEIC", 
    "NESTLE": "NTLC", "NSIA": "NSBC", "ONATEL": "ONTBF", "ORAGROUP": "ORGT",
    "ORANGE": "ORAC", "PALM": "PALC", "SAFCA": "SAFC", "SAPH": "SPHC", 
    "SERVAIR": "ABJC", "SETAO": "STAC", "SOCIETE GENERALE": "SGBC", 
    "SGBCI": "SGBC", "SICABLE": "CABC", "SICOR": "SICC", "SITAB": "STBC", 
    "SMB": "SMBC", "SOCIETE IVOIRIENNE DE BANQUE": "SIBC", "SONATEL": "SNTS",
    "TOTAL CI": "TTLC", "TOTAL SN": "TTLS", "UNILEVER": "UNLC", "VIVO": "SHEC"
}

FUNDAMENTALS = {
    "SNTS": {"div": 1500, "per": 7.8, "detachement": "15/05/2026", "paiement": "28/05/2026"},
    "ORAC": {"div": 1500, "per": 9.2, "detachement": "02/06/2026", "paiement": "16/06/2026"},
    "SGBC": {"div": 2100, "per": 6.5, "detachement": "12/07/2026", "paiement": "26/07/2026"},
    "SIBC": {"div": 720, "per": 7.1, "detachement": "18/06/2026", "paiement": "02/07/2026"},
    "BOAC": {"div": 910, "per": 8.0, "detachement": "05/05/2026", "paiement": "19/05/2026"},
    "BOABF": {"div": 800, "per": 6.9, "detachement": "10/05/2026", "paiement": "24/05/2026"},
    "BOAB": {"div": 750, "per": 7.2, "detachement": "14/05/2026", "paiement": "28/05/2026"},
    "BOAM": {"div": 550, "per": 7.5, "detachement": "20/05/2026", "paiement": "03/06/2026"},
    "BOAN": {"div": 480, "per": 6.8, "detachement": "22/05/2026", "paiement": "05/06/2026"},
    "BOAS": {"div": 620, "per": 8.1, "detachement": "25/05/2026", "paiement": "08/06/2026"},
    "ECOC": {"div": 1250, "per": 6.2, "detachement": "08/06/2026", "paiement": "22/06/2026"},
    "NSBC": {"div": 1350, "per": 7.0, "detachement": "15/06/2026", "paiement": "29/06/2026"},
    "CBIBF": {"div": 2200, "per": 8.5, "detachement": "11/06/2026", "paiement": "25/06/2026"},
    "PALC": {"div": 650, "per": 5.4, "detachement": "18/07/2026", "paiement": "01/08/2026"},
    "SPHC": {"div": 500, "per": 6.1, "detachement": "22/07/2026", "paiement": "05/08/2026"},
    "TTLC": {"div": 180, "per": 9.0, "detachement": "10/08/2026", "paiement": "24/08/2026"},
    "TTLS": {"div": 210, "per": 8.7, "detachement": "12/08/2026", "paiement": "26/08/2026"},
    "NTLC": {"div": 950, "per": 10.2, "detachement": "02/09/2026", "paiement": "16/09/2026"},
    "CIEC": {"div": 520, "per": 7.9, "detachement": "14/06/2026", "paiement": "28/06/2026"},
    "ONTBF": {"div": 200, "per": 7.4, "detachement": "18/05/2026", "paiement": "01/06/2026"},
    "SMBC": {"div": 1100, "per": 8.8, "detachement": "08/09/2026", "paiement": "22/09/2026"},
    "STBC": {"div": 1400, "per": 9.5, "detachement": "04/07/2026", "paiement": "18/07/2026"},
    "BICC": {"div": 1800, "per": 8.3, "detachement": "20/06/2026", "paiement": "04/07/2026"},
    "CABC": {"div": 220, "per": 7.6, "detachement": "16/06/2026", "paiement": "30/06/2026"}
}

def scraper_brvm_complet():
    url = "https://www.sikafinance.com/marches/aaz"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    print("🔄 Extraction des cours en direct & mise à jour des fondamentaux...")
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("❌ Connexion échouée.")
        return

    soup = BeautifulSoup(res.text, "html.parser")
    tables = soup.find_all("table")

    donnees = []

    for table in tables:
        for row in table.find_all("tr"):
            cols = [td.text.strip() for td in row.find_all("td")]
            if len(cols) >= 8:
                nom = cols[0].upper()

                if any(k in nom for k in ["BRVM", "INDICE", "SIKA", "SECTEUR", "COMPOSITE"]):
                    continue

                try:
                    cours_str = cols[6].replace(" ", "").replace("\xa0", "").replace(",", ".").replace("FCFA", "")
                    var_str = cols[7].replace(" ", "").replace("\xa0", "").replace(",", ".").replace("%", "")

                    cours = float(cours_str)
                    var = float(var_str)

                    if cours <= 0:
                        continue

                    ticker = nom
                    for cle, symbol in TICKER_MAP.items():
                        if cle in nom:
                            ticker = symbol
                            break

                    f = FUNDAMENTALS.get(ticker, {"div": 0, "per": None, "detachement": "À préciser", "paiement": "À préciser"})
                    
                    div_net = f["div"]
                    per = f["per"]
                    rendement = round((div_net / cours) * 100, 2) if div_net > 0 else None

                    donnees.append({
                        "Ticker": ticker,
                        "Cours (FCFA)": int(cours),
                        "Variation (%)": var,
                        "PER (x)": per if per else "—",
                        "Rendement (%)": f"{rendement:.2f} %" if rendement else "—",
                        "Dividende Net": f"{div_net} FCFA" if div_net > 0 else "À préciser",
                        "Détachement Coupon": f["detachement"],
                        "Paiement Effectif": f["paiement"]
                    })
                except ValueError:
                    continue

    if not donnees:
        print("❌ Aucune donnée collectée.")
        return

    df = pd.DataFrame(donnees).drop_duplicates(subset=["Ticker"])
    print(f"✅ {len(df)} actions enrichies avec succès !")

    # Enregistrement sécurisé dans les bases SQLite
    for db in ["brvm.db", "data/brvm.db"]:
        try:
            conn = sqlite3.connect(db)
            df.to_sql("cours", conn, if_exists="replace", index=False)
            df.to_sql("screening", conn, if_exists="replace", index=False)
            conn.close()
        except Exception as e:
            print(f"Avertissement écriture DB ({db}): {e}")

if __name__ == "__main__":
    scraper_brvm_complet()