import sqlite3
import pandas as pd
from datetime import date

def sauvegarder_historique(conn):
    """Enregistre le cours et la variation du jour dans la table historique."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            date TEXT,
            ticker TEXT,
            cours REAL,
            variation REAL,
            PRIMARY KEY (date, ticker)
        )
    """)
    
    # Récupération des cours actuels dans la table screening
    df_current = pd.read_sql("SELECT Ticker, `Cours (FCFA)`, `Variation (%)` FROM screening", conn)
    today = date.today().isoformat()
    
    for _, row in df_current.iterrows():
        ticker = row["Ticker"]
        cours = float(row.get("Cours (FCFA)", 0.0))
        var = float(row.get("Variation (%)", 0.0))
        if ticker:
            cursor.execute("""
                INSERT OR REPLACE INTO historique (date, ticker, cours, variation)
                VALUES (?, ?, ?, ?)
            """, (today, ticker, cours, var))
            
    conn.commit()

def scraper_brvm_live():
    """Effectue le scraping en direct et met à jour SQLite."""
    # Placez ici votre logique d'extraction web actuelle
    # Exemple de structure de sauvegarde :
    conn = sqlite3.connect("brvm.db")
    
    # 1. Mise à jour de la table principale 'screening'
    # df_scraped.to_sql("screening", conn, if_exists="replace", index=False)
    
    # 2. Historisation automatique des prix du jour
    sauvegarder_historique(conn)
    
    conn.close()

if __name__ == "__main__":
    scraper_brvm_live()