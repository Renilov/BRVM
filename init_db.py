import sqlite3
import pandas as pd

# 1. Données complètes des actions de la BRVM
actions_brvm = [
    # --- FINANCE ---
    {"ticker": "BOAB", "nom": "Bank of Africa Bénin", "pays": "Bénin", "secteur": "Finance", "dernier_dividende_net": 610.0},
    {"ticker": "BOBF", "nom": "Bank of Africa Burkina Faso", "pays": "Burkina Faso", "secteur": "Finance", "dernier_dividende_net": 580.0},
    {"ticker": "BOCI", "nom": "Bank of Africa Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 700.0},
    {"ticker": "BOAM", "nom": "Bank of Africa Mali", "pays": "Mali", "secteur": "Finance", "dernier_dividende_net": 270.0},
    {"ticker": "BOAN", "nom": "Bank of Africa Niger", "pays": "Niger", "secteur": "Finance", "dernier_dividende_net": 530.0},
    {"ticker": "BOAS", "nom": "Bank of Africa Sénégal", "pays": "Sénégal", "secteur": "Finance", "dernier_dividende_net": 170.0},
    {"ticker": "CBIB", "nom": "Coris Bank International", "pays": "Burkina Faso", "secteur": "Finance", "dernier_dividende_net": 540.0},
    {"ticker": "ETIT", "nom": "Ecobank Transnational Inc.", "pays": "Togo", "secteur": "Finance", "dernier_dividende_net": 1.1},
    {"ticker": "NSBC", "nom": "NSIA Banque Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 500.0},
    {"ticker": "ORGT", "nom": "Oragroup Togo", "pays": "Togo", "secteur": "Finance", "dernier_dividende_net": 0.0},
    {"ticker": "SAFC", "nom": "SAFCA CI", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 0.0},
    {"ticker": "SGBC", "nom": "Société Générale Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 1150.0},
    {"ticker": "SIBC", "nom": "Société Ivoirienne de Banque", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 315.0},
    {"ticker": "BICC", "nom": "BICICI", "pays": "Côte d'Ivoire", "secteur": "Finance", "dernier_dividende_net": 630.0},

    # --- SERVICES PUBLICS (TELECOM, ÉNERGIE, EAU) ---
    {"ticker": "SNTS", "nom": "Sonatel", "pays": "Sénégal", "secteur": "Services Publics", "dernier_dividende_net": 1575.0},
    {"ticker": "ONTBF", "nom": "Onatel Burkina Faso", "pays": "Burkina Faso", "secteur": "Services Publics", "dernier_dividende_net": 180.0},
    {"ticker": "CIEC", "nom": "CIE Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Services Publics", "dernier_dividende_net": 150.0},
    {"ticker": "SDCC", "nom": "SODECI", "pays": "Côte d'Ivoire", "secteur": "Services Publics", "dernier_dividende_net": 400.0},

    # --- INDUSTRIE ---
    {"ticker": "NTLC", "nom": "Nestlé Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 680.0},
    {"ticker": "SLBC", "nom": "Solibra CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 4000.0},
    {"ticker": "CABC", "nom": "Sicable CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 75.0},
    {"ticker": "SICC", "nom": "SIVOM", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 0.0},
    {"ticker": "STBC", "nom": "SITAB CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 500.0},
    {"ticker": "UNLC", "nom": "Unilever CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 0.0},
    {"ticker": "NEIC", "nom": "NEI-CEDA CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 40.0},
    {"ticker": "SEMC", "nom": "Crown SIEM CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 0.0},
    {"ticker": "FTSC", "nom": "Filtisac CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 120.0},
    {"ticker": "SMBC", "nom": "SMB CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 450.0},
    {"ticker": "TCHC", "nom": "Trituraf CI", "pays": "Côte d'Ivoire", "secteur": "Industrie", "dernier_dividende_net": 0.0},

    # --- DISTRIBUTION & COMMERCE ---
    {"ticker": "TTLC", "nom": "TotalEnergies Côte d'Ivoire", "pays": "Côte d'Ivoire", "secteur": "Distribution", "dernier_dividende_net": 180.0},
    {"ticker": "TTLS", "nom": "TotalEnergies Sénégal", "pays": "Sénégal", "secteur": "Distribution", "dernier_dividende_net": 160.0},
    {"ticker": "SHEC", "nom": "Vivo Energy CI", "pays": "Côte d'Ivoire", "secteur": "Distribution", "dernier_dividende_net": 65.0},
    {"ticker": "PRSC", "nom": "Bernabé CI", "pays": "Côte d me d'Ivoire", "secteur": "Distribution", "dernier_dividende_net": 150.0},
    {"ticker": "CFAC", "nom": "CFAO Motors CI", "pays": "Côte d'Ivoire", "secteur": "Distribution", "dernier_dividende_net": 60.0},
    {"ticker": "ABJC", "nom": "Servair Abidjan", "pays": "Côte d'Ivoire", "secteur": "Distribution", "dernier_dividende_net": 95.0},

    # --- AGRICULTURE ---
    {"ticker": "PALC", "nom": "Palm CI", "pays": "Côte d'Ivoire", "secteur": "Agriculture", "dernier_dividende_net": 1200.0},
    {"ticker": "SOGC", "nom": "SOGB CI", "pays": "Côte d'Ivoire", "secteur": "Agriculture", "dernier_dividende_net": 450.0},
    {"ticker": "SIPC", "nom": "SAPH CI", "pays": "Côte d'Ivoire", "secteur": "Agriculture", "dernier_dividende_net": 320.0},
    {"ticker": "SICC", "nom": "SICOR CI", "pays": "Côte d'Ivoire", "secteur": "Agriculture", "dernier_dividende_net": 0.0},
    {"ticker": "SPHC", "nom": "SAPH CI (PF)", "pays": "Côte d'Ivoire", "secteur": "Agriculture", "dernier_dividende_net": 0.0},

    # --- TRANSPORT & LOGISTIQUE ---
    {"ticker": "SDSC", "nom": "Bolloré Transport & Logistics CI (AGL)", "pays": "Côte d'Ivoire", "secteur": "Transport", "dernier_dividende_net": 100.0},
    {"ticker": "SVOC", "nom": "Movia CI (ex-Movima)", "pays": "Côte d'Ivoire", "secteur": "Transport", "dernier_dividende_net": 0.0},

    # --- IMMOBILIER ---
    {"ticker": "SCCI", "nom": "SICABLE / SOGB Immobilier", "pays": "Côte d'Ivoire", "secteur": "Immobilier", "dernier_dividende_net": 0.0}
]

# 2. Création et stockage en base SQLite
def initialiser_base():
    conn = sqlite3.connect("brvm_invest.db")
    df = pd.DataFrame(actions_brvm)
    
    # Injection dans la table 'actions'
    df.to_sql("actions", conn, if_exists="replace", index=False)
    conn.close()
    print("✅ Base de données SQLite 'brvm_invest.db' créée avec succès !")

if __name__ == "__main__":
    initialiser_base()