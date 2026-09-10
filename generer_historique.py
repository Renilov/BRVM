import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DB_FILE = "brvm_invest.db"

def corriger_table_et_simuler():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Supprimer l'ancienne table si elle est mal structurée
    cursor.execute("DROP TABLE IF EXISTS historique_cours")
    
    # 2. Recréer la table correctement
    cursor.execute("""
        CREATE TABLE historique_cours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            date_releve TEXT NOT NULL,
            cours REAL NOT NULL,
            UNIQUE(ticker, date_releve)
        )
    """)
    conn.commit()
    
    # 3. Récupérer la liste des actions
    cursor.execute("SELECT ticker, cours_actuel FROM actions WHERE cours_actuel > 0")
    actions = cursor.fetchall()
    
    if not actions:
        print("⚠️ Aucune action trouvée dans la table 'actions'.")
        conn.close()
        return

    today = datetime.now()
    
    # 4. Générer 30 jours d'historique fictif pour chaque action
    for ticker, cours in actions:
        for i in range(30, -1, -1):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            variation = 1 + np.random.uniform(-0.02, 0.02)
            cours_simule = round(cours * variation, 0)
            
            cursor.execute("""
                INSERT OR REPLACE INTO historique_cours (ticker, date_releve, cours)
                VALUES (?, ?, ?)
            """, (ticker, date_str, cours_simule))
            
    conn.commit()
    conn.close()
    print("✅ Table réinitialisée et historique sur 30 jours généré avec succès !")

if __name__ == "__main__":
    corriger_table_et_simuler()