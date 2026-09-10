import os
import sqlite3
import requests

# Clés de connexion Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8868543631:AAGA20vRxc60ExisDDHdJ3qFUsLn6-f-ceI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6771361991")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erreur envoi Telegram : {e}")
        return False

def verifier_et_envoyer_alertes():
    conn = sqlite3.connect("brvm.db")
    cursor = conn.cursor()

    try:
        # Sélection des actions ayant bougé de 2% ou plus
        cursor.execute("""
            SELECT Ticker, `Cours (FCFA)`, `Variation (%)` 
            FROM screening 
            WHERE ABS(`Variation (%)`) >= 2.0
            ORDER BY `Variation (%)` DESC
        """)
        mouvements = cursor.fetchall()
    except Exception as e:
        print(f"Erreur lecture SQLite : {e}")
        mouvements = []
    finally:
        conn.close()

    if mouvements:
        msg = "📊 *BRVM QUANTUM - ALERTES DU JOUR*\n\n"
        for ticker, cours, var in mouvements:
            emoji = "🚀" if var > 0 else "🔻"
            msg += f"{emoji} *{ticker}* : {cours:,.0f} FCFA ({var:+.2f}%)\n"
        envoyer_telegram(msg)
    else:
        envoyer_telegram("📊 *BRVM QUANTUM* : Clôture du marché. Aucun mouvement majeur (≥ 2%) aujourd'hui.")

if __name__ == "__main__":
    verifier_et_envoyer_alertes()