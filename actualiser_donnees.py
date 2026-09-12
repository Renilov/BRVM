import sqlite3
import urllib.request
import ssl
import re
import json
from bs4 import BeautifulSoup

DB_FILE = "brvm.db"

def nettoyer_nombre(valeur_str):
    if not valeur_str:
        return 0.0
    clean = re.sub(r'[^\d,-]', '', str(valeur_str)).replace(',', '.')
    try:
        return float(clean)
    except ValueError:
        return 0.0

def niveau_1_api_brvm():
    """Tentative 1 : Interception directe du flux JSON / API de la BRVM"""
    url_api = "https://www.brvm.org/fr/cours-et-cotations/cours-du-jour"
    results = {}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'X-Requested-With': 'XMLHttpRequest'
        }
        req = urllib.request.Request(url_api, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            content = resp.read().decode('utf-8')
            # Recherche de données JSON encapsulées dans la page
            json_matches = re.findall(r'\{"ticker":"([^"]+)".*?"cours":([\d\.]+).*?"variation":([\d\.-]+).*?"volume":([\d]+)\}', content)
            for ticker, cours, var, vol in json_matches:
                results[ticker.upper()] = {
                    "cours": float(cours),
                    "variation": float(var),
                    "volume": int(vol)
                }
    except Exception:
        pass
    return results

def niveau_2_scraper_miroir():
    """Tentative 2 : Extraction sur un site miroir d'informations boursières"""
    url_miroir = "https://www.richbourse.com/fr/bourse/cours"
    results = {}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url_miroir, headers=headers)
        
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            soup = BeautifulSoup(resp.read(), 'html.parser')
            rows = soup.find_all('tr')
            for row in rows:
                cols = [c.text.strip() for c in row.find_all('td')]
                if len(cols) >= 4:
                    ticker = cols[0].strip().upper()
                    if len(ticker) == 4 and ticker.isalpha():
                        cours = nettoyer_nombre(cols[1])
                        var = nettoyer_nombre(cols[2])
                        vol = int(nettoyer_nombre(cols[3]))
                        if cours > 0:
                            results[ticker] = {"cours": cours, "variation": var, "volume": vol}
    except Exception:
        pass
    return results

def synchroniser_brvm_web():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    source_utilisee = "Niveau 1 (API Directe BRVM)"
    donnees_live = niveau_1_api_brvm()

    if not donnees_live:
        source_utilisee = "Niveau 2 (Miroir Boursier)"
        donnees_live = niveau_2_scraper_miroir()

    if not donnees_live:
        conn.close()
        return True, "Niveau 3 : Pas de connexion réseau ou site inaccessible. Vos données SQLite existantes restent intactes."

    mises_a_jour = 0
    for ticker, info in donnees_live.items():
        cursor.execute("SELECT ticker FROM actions WHERE ticker = ?", (ticker,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE actions
                SET cours_actuel = ?
                WHERE ticker = ?
            """, (info["cours"], ticker))

            cursor.execute("""
                UPDATE screening
                SET "Cours (FCFA)" = ?,
                    "Variation (%)" = ?,
                    Volume = ?
                WHERE Ticker = ?
            """, (info["cours"], info["variation"], info["volume"], ticker))
            mises_a_jour += 1

    conn.commit()
    conn.close()

    return True, f"Succès ({source_utilisee}) : {mises_a_jour} actions actualisées en direct !"

if __name__ == "__main__":
    statut, msg = synchroniser_brvm_web()
    print(msg)