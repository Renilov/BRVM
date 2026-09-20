import datetime
import sqlite3
import time
import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

DB_NAME = "brvm.db"
URL_BRVM = "https://www.brvm.org/fr/cours-du-jour"

OFFICIAL_BRVM_TICKERS = {
    "ABJC",
    "BICB",
    "BICC",
    "BNBC",
    "BOAB",
    "BOAC",
    "BOAM",
    "BOAN",
    "BOAS",
    "CABC",
    "CFAC",
    "CIEC",
    "ECOC",
    "ETIT",
    "FTSC",
    "LNBB",
    "NEIC",
    "NSBC",
    "NTLC",
    "ORAC",
    "ORGT",
    "PALC",
    "PRSC",
    "SAFC",
    "SCRC",
    "SDCC",
    "SDSC",
    "SEMC",
    "SGBC",
    "SHEC",
    "SIBC",
    "SICC",
    "SIVC",
    "SLBC",
    "SMBC",
    "SNTS",
    "SOGC",
    "SPHC",
    "STAC",
    "STBC",
    "TTLC",
    "TTLS",
    "UNLC",
    "UNXC",
}


def initialiser_scraper_anti_waf():
    """Crée un scraper simulant fidèlement un navigateur Chrome sous Windows"""
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True},
        delay=5,
    )


def scraper_brvm_anti_parefeu():
    scraper = initialiser_scraper_anti_waf()
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    print(f"🌐 Passage des pare-feu et connexion à {URL_BRVM}...")

    try:
        # Pause humaine avant requête
        time.sleep(2)
        response = scraper.get(URL_BRVM, timeout=20)

        if response.status_code != 200:
            print(
                f"❌ Accès refusé par le pare-feu (Code HTTP : {response.status_code})"
            )
            return pd.DataFrame()

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table")

        if not table:
            print(
                "⚠️ Page chargée mais tableau introuvable (vérifiez si le contenu nécessite JS)."
            )
            return pd.DataFrame()

        dfs = pd.read_html(str(table))
        if not dfs:
            return pd.DataFrame()

        df_raw = dfs[0]
        donnees = []

        for _, row in df_raw.iterrows():
            row_str = [str(val).strip() for val in row.values]

            # Vérification de la présence du ticker
            ticker = next(
                (
                    cell.upper()
                    for cell in row_str
                    if cell.upper() in OFFICIAL_BRVM_TICKERS
                ),
                None,
            )

            if ticker:
                donnees.append(
                    {
                        "Ticker": ticker,
                        "Nom": ticker,
                        "Cours (FCFA)": row_str[3] if len(row_str) > 3 else "0",
                        "Variation (%)": (
                            row_str[4] if len(row_str) > 4 else "0"
                        ),
                        "Volume": row_str[5] if len(row_str) > 5 else "0",
                        "PER": "à déterminer",
                        "Dividende": "à déterminer",
                        "Date de détachement": "à déterminer",
                        "Date de paiement": "à déterminer",
                        "date_maj": today_str,
                    }
                )

        df = pd.DataFrame(donnees)
        return (
            df.drop_duplicates(subset=["Ticker"], keep="first")
            if not df.empty
            else df
        )

    except Exception as e:
        print(f"❌ Blocage du pare-feu rencontré : {e}")
        return pd.DataFrame()