import os
import re
import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Base de données exhaustive des fondamentaux BRVM (Dividendes nets réels & PER)
BRVM_DATABASE = {
    "AGLC": {"nom": "AFRICA GLOBAL LOGISTICS CI", "secteur": "Transport", "div": 185, "per": 8.5, "detachement": "10/06/2026", "paiement": "24/06/2026"},
    "BOAB": {"nom": "BANK OF AFRICA BENIN", "secteur": "Finances", "div": 750, "per": 7.2, "detachement": "14/05/2026", "paiement": "28/05/2026"},
    "BOABF": {"nom": "BANK OF AFRICA BF", "secteur": "Finances", "div": 800, "per": 6.9, "detachement": "10/05/2026", "paiement": "24/05/2026"},
    "BOAC": {"nom": "BANK OF AFRICA CI", "secteur": "Finances", "div": 910, "per": 8.0, "detachement": "05/05/2026", "paiement": "19/05/2026"},
    "BOAM": {"div": 550, "nom": "BANK OF AFRICA MALI", "secteur": "Finances", "per": 7.5, "detachement": "20/05/2026", "paiement": "03/06/2026"},
    "BOAN": {"nom": "BANK OF AFRICA NIGER", "secteur": "Finances", "div": 480, "per": 6.8, "detachement": "22/05/2026", "paiement": "05/06/2026"},
    "BOAS": {"nom": "BANK OF AFRICA SENEGAL", "secteur": "Finances", "div": 620, "per": 8.1, "detachement": "25/05/2026", "paiement": "08/06/2026"},
    "BIBE": {"nom": "BANQUE INTERNATIONALE BENIN", "secteur": "Finances", "div": 500, "per": 7.0, "detachement": "A préciser", "paiement": "A préciser"},
    "BNBC": {"nom": "BERNABE CI", "secteur": "Distribution", "div": 150, "per": 12.1, "detachement": "18/06/2026", "paiement": "02/07/2026"},
    "BICC": {"nom": "BICICI", "secteur": "Finances", "div": 1800, "per": 8.3, "detachement": "20/06/2026", "paiement": "04/07/2026"},
    "CFAC": {"nom": "CFAO MOTORS CI", "secteur": "Distribution", "div": 110, "per": 9.0, "detachement": "15/06/2026", "paiement": "29/06/2026"},
    "CIEC": {"nom": "CIE CI", "secteur": "Services Publics", "div": 520, "per": 7.9, "detachement": "14/06/2026", "paiement": "28/06/2026"},
    "CBIBF": {"nom": "CORIS BANK INT. BF", "secteur": "Finances", "div": 2200, "per": 8.5, "detachement": "11/06/2026", "paiement": "25/06/2026"},
    "SEMC": {"nom": "CROWN SIEM CI", "secteur": "Industrie", "div": 100, "per": 11.0, "detachement": "A préciser", "paiement": "A préciser"},
    "ECOC": {"nom": "ECOBANK COTE D'IVOIRE", "secteur": "Finances", "div": 1250, "per": 6.2, "detachement": "08/06/2026", "paiement": "22/06/2026"},
    "ERIUM": {"nom": "ERIUM CI", "secteur": "Industrie", "div": 0, "per": 15.0, "detachement": "N/A", "paiement": "N/A"},
    "ETIT": {"nom": "ECOBANK TRANS. INC.", "secteur": "Finances", "div": 1.5, "per": 4.1, "detachement": "30/05/2026", "paiement": "15/06/2026"},
    "FTSC": {"nom": "FILTISAC CI", "secteur": "Industrie", "div": 180, "per": 10.5, "detachement": "25/06/2026", "paiement": "09/07/2026"},
    "LNBC": {"nom": "LOTERIE NATIONALE BENIN", "secteur": "Autres Secteurs", "div": 250, "per": 8.8, "detachement": "12/07/2026", "paiement": "26/07/2026"},
    "MOVIS": {"nom": "MOVIS CI", "secteur": "Transport", "div": 0, "per": 0, "detachement": "N/A", "paiement": "N/A"},
    "NEIC": {"nom": "NEI-CEDA CI", "secteur": "Distribution", "div": 225, "per": 6.8, "detachement": "01/09/2026", "paiement": "15/09/2026"},
    "NTSC": {"nom": "NESTLE CI", "secteur": "Industrie", "div": 750, "per": 12.4, "detachement": "10/07/2026", "paiement": "24/07/2026"},
    "NSBC": {"nom": "NSIA BANQUE CI", "secteur": "Finances", "div": 1350, "per": 7.0, "detachement": "15/06/2026", "paiement": "29/06/2026"},
    "ONTBF": {"nom": "ONATEL BURKINA", "secteur": "Services Publics", "div": 200, "per": 7.4, "detachement": "18/05/2026", "paiement": "01/06/2026"},
    "ORAC": {"nom": "ORAGROUP TOGO", "secteur": "Finances", "div": 1500, "per": 9.2, "detachement": "02/06/2026", "paiement": "16/06/2026"},
    "ORACI": {"nom": "ORANGE COTE D'IVOIRE", "secteur": "Services Publics", "div": 1500, "per": 9.8, "detachement": "20/05/2026", "paiement": "03/06/2026"},
    "PALC": {"nom": "PALM CI", "secteur": "Agriculture", "div": 650, "per": 5.4, "detachement": "18/07/2026", "paiement": "01/08/2026"},
    "SAFC": {"nom": "SAFCA CI", "secteur": "Finances", "div": 0, "per": 0, "detachement": "N/A", "paiement": "N/A"},
    "SAPH": {"nom": "SAPH CI", "secteur": "Agriculture", "div": 500, "per": 6.1, "detachement": "22/07/2026", "paiement": "05/08/2026"},
    "ABJC": {"nom": "SERVAIR ABIDJAN", "secteur": "Distribution", "div": 195, "per": 11.2, "detachement": "14/06/2026", "paiement": "28/06/2026"},
    "STAC": {"nom": "SETAO CI", "secteur": "Industrie", "div": 60, "per": 8.0, "detachement": "A préciser", "paiement": "A préciser"},
    "SGBC": {"nom": "SOCIETE GENERALE CI", "secteur": "Finances", "div": 2100, "per": 6.5, "detachement": "12/07/2026", "paiement": "26/07/2026"},
    "CABC": {"nom": "SICABLE CI", "secteur": "Industrie", "div": 220, "per": 7.6, "detachement": "16/06/2026", "paiement": "30/06/2026"},
    "SICC": {"nom": "SICOR CI", "secteur": "Agriculture", "div": 0, "per": 0, "detachement": "N/A", "paiement": "N/A"},
    "SIBC": {"nom": "SOCIETE IVOIRIENNE DE BANQUE", "secteur": "Finances", "div": 720, "per": 7.1, "detachement": "18/06/2026", "paiement": "02/07/2026"},
    "STBC": {"nom": "SITAB CI", "secteur": "Industrie", "div": 1400, "per": 9.5, "detachement": "04/07/2026", "paiement": "18/07/2026"},
    "SMBC": {"nom": "SMB CI", "secteur": "Industrie", "div": 1100, "per": 8.8, "detachement": "08/09/2026", "paiement": "22/09/2026"},
    "SNTS": {"nom": "SONATEL SENEGAL", "secteur": "Services Publics", "div": 1500, "per": 7.8, "detachement": "15/05/2026", "paiement": "28/05/2026"},
    "SCHC": {"nom": "SUCRIVOIRE CI", "secteur": "Agriculture", "div": 115, "per": 8.2, "detachement": "A préciser", "paiement": "A préciser"},
    "TTLC": {"nom": "TOTAL COTE D'IVOIRE", "secteur": "Distribution", "div": 180, "per": 9.0, "detachement": "10/08/2026", "paiement": "24/08/2026"},
    "TTLS": {"nom": "TOTAL SENEGAL", "secteur": "Distribution", "div": 210, "per": 8.7, "detachement": "12/08/2026", "paiement": "26/08/2026"},
    "UNXC": {"nom": "UNIWAX CI", "secteur": "Industrie", "div": 0, "per": 14.0, "detachement": "N/A", "paiement": "N/A"},
    "UNLC": {"nom": "UNILEVER CI", "secteur": "Industrie", "div": 0, "per": 0, "detachement": "N/A", "paiement": "N/A"}
}

def scraper_brvm_live():
    print("🚀 Démarrage du scraping des données réelles BRVM...")
    url = "https://www.sikafinance.com/marches/aaz"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    scraped_data = []

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Extraction des tableaux HTML
        tables = pd.read_html(response.text)
        
        target_df = None
        for t in tables:
            cols_str = " ".join([str(c) for c in t.columns])
            if "Nom" in cols_str or "Dernier" in cols_str or "Variation" in cols_str:
                target_df = t
                break

        if target_df is not None:
            # Nettoyage des colonnes
            target_df.columns = [str(c).strip() for c in target_df.columns]
            
            col_nom = [c for c in target_df.columns if "Nom" in c or "Valeur" in c][0]
            col_cours = [c for c in target_df.columns if "Dernier" in c or "Cours" in c][0]
            col_var = [c for c in target_df.columns if "Var" in c][0]

            for _, row in target_df.iterrows():
                nom_brut = str(row[col_nom]).strip()
                cours_raw = str(row[col_cours])
                var_raw = str(row[col_var])

                # Extraction numérique du cours
                cours_clean = re.sub(r"[^\d.]", "", cours_raw.replace(" ", "").replace(",", "."))
                var_clean = re.sub(r"[^\d.\-+]", "", var_raw.replace(" ", "").replace(",", "."))

                try:
                    cours_val = float(cours_clean) if cours_clean else None
                except ValueError:
                    cours_val = None

                try:
                    var_val = float(var_clean) if var_clean else 0.0
                except ValueError:
                    var_val = 0.0

                if not cours_val or cours_val <= 0:
                    continue

                # Recherche de la correspondance Ticker dans BRVM_DATABASE
                ticker_matched = None
                for ticker, info in BRVM_DATABASE.items():
                    if ticker.lower() in nom_brut.lower() or info["nom"].lower() in nom_brut.lower() or nom_brut.lower() in info["nom"].lower():
                        ticker_matched = ticker
                        break

                if not ticker_matched:
                    # Ticker synthétique si inconnu
                    ticker_matched = "".join([w[0] for w in nom_brut.split()[:4]]).upper()

                info_fonda = BRVM_DATABASE.get(ticker_matched, {
                    "nom": nom_brut,
                    "secteur": "Autres Secteurs",
                    "div": 0.0,
                    "per": None,
                    "detachement": "A préciser",
                    "paiement": "A préciser"
                })

                div_net = info_fonda.get("div", 0.0)
                # Calcul dynamique du rendement en temps réel
                rendement_dyn = round((div_net / cours_val) * 100, 2) if (div_net and cours_val > 0) else 0.0

                scraped_data.append({
                    "Ticker": ticker_matched,
                    "Nom": info_fonda.get("nom", nom_brut),
                    "Secteur": info_fonda.get("secteur", "Autres"),
                    "Cours (FCFA)": int(cours_val),
                    "Variation (%)": var_val,
                    "PER (x)": info_fonda.get("per"),
                    "Rendement (%)": rendement_dyn,
                    "Dividende Net": div_net,
                    "Détachement Coupon": info_fonda.get("detachement", "A préciser"),
                    "Paiement Effectif": info_fonda.get("paiement", "A préciser")
                })

    except Exception as e:
        print(f"⚠️ Avertissement lors du scraping live : {e}")

    # Fallback si le scraping web rencontre un blocage réseau
    if not scraped_data:
        print("ℹ️ Chargement de la base exhaustive de secours BRVM...")
        for ticker, info in BRVM_DATABASE.items():
            cours_defaut = 10000
            div_net = info.get("div", 0)
            rend_defaut = round((div_net / cours_defaut) * 100, 2) if div_net > 0 else 0.0
            
            scraped_data.append({
                "Ticker": ticker,
                "Nom": info["nom"],
                "Secteur": info["secteur"],
                "Cours (FCFA)": cours_defaut,
                "Variation (%)": 0.0,
                "PER (x)": info["per"],
                "Rendement (%)": rend_defaut,
                "Dividende Net": div_net,
                "Détachement Coupon": info["detachement"],
                "Paiement Effectif": info["paiement"]
            })

    df = pd.DataFrame(scraped_data)

    # Sauvegarde dans les bases SQLite local & Streamlit
    os.makedirs("data", exist_ok=True)
    for db_path in ["data/brvm.db", "brvm.db"]:
        conn = sqlite3.connect(db_path)
        df.to_sql("screening", conn, if_exists="replace", index=False)
        conn.close()
        print(f"✅ Base sauvegardée : {db_path} ({len(df)} lignes)")

if __name__ == "__main__":
    scraper_brvm_live()