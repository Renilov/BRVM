import os
import requests

# ==========================================
# CONFIGURATION DES IDENTIFIANTS (LOCAL & CLOUD)
# ==========================================

# 1. Telegram
# Lit la clé depuis les variables d'environnement Cloud (GitHub Secrets) s'il y en a une,
# sinon utilise vos identifiants locaux par défaut.
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", 
    "8868543631:AAGA20vRxc60ExisDDHdJ3qFUsLn6-f-ceI"
)
TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID", 
    "6771361991"
)

# 2. WhatsApp (Twilio API - Optionnel)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
WHATSAPP_TO = os.getenv("WHATSAPP_TO", "whatsapp:+2250000000000")


def send_telegram_alert(message: str) -> bool:
    """
    Envoie un message instantané via le Bot Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "VOTRE_TOKEN_BOTFATHER":
        print("⚠️ Attention : TELEGRAM_BOT_TOKEN est invalide ou manquant.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Alerte Telegram envoyée avec succès !")
            return True
        else:
            print(f"❌ Erreur Telegram ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur de connexion Telegram : {e}")
        return False


def send_whatsapp_alert(message: str) -> bool:
    """
    Envoie une alerte WhatsApp via Twilio API (Optionnel).
    """
    if not TWILIO_ACCOUNT_SID or TWILIO_ACCOUNT_SID == "VOTRE_TWILIO_ACCOUNT_SID":
        return False
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": WHATSAPP_TO,
        "Body": message
    }
    
    try:
        response = requests.post(
            url, 
            data=data, 
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), 
            timeout=10
        )
        if response.status_code in [200, 201]:
            print("✅ Alerte WhatsApp envoyée avec succès !")
            return True
        else:
            return False
    except Exception:
        return False


def dispatch_alert(title: str, body: str) -> bool:
    """
    Diffuse l'alerte sur Telegram (et WhatsApp le cas échéant).
    """
    formatted_msg = f"📊 *BRVM QUANTUM INSTITUTIONAL*\n\n🔔 *{title}*\n{body}"
    
    tg_status = send_telegram_alert(formatted_msg)
    wa_status = send_whatsapp_alert(formatted_msg)
    
    return tg_status or wa_status


if __name__ == "__main__":
    # Test d'envoi rapide
    print("🧪 Test de diffusion de l'alerte sécurisée...")
    dispatch_alert(
        "Sécurité Cloud Validée", 
        "🚀 Le fichier alerts.py est prêt pour le fonctionnement local et le déploiement automatisé sur GitHub Actions !"
    )