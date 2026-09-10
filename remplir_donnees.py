import sqlite3

DB_FILE = "brvm_invest.db"

def injecter_donnees_brvm():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Données réalistes d'entreprises BRVM
    actions_data = [
        ("SNTS", "Sonatel Côte d'Ivoire / Sénégal", "Services Publics", 18500, 1575, 8.51, "2026-05-12", "2026-05-28"),
        ("SGBC", "Société Générale Côte d'Ivoire", "Finance", 16800, 1250, 7.44, "2026-06-01", "2026-06-15"),
        ("PALC", "Palm Côte d'Ivoire", "Agriculture", 7200, 800, 11.11, "2026-06-10", "2026-06-25"),
        ("ETIT", "Ecobank Transnational Incorporated", "Finance", 19, 2, 10.53, "2026-05-20", "2026-06-05"),
        ("BOAB", "Bank Of Africa Bénin", "Finance", 6900, 610, 8.84, "2026-04-18", "2026-05-02"),
        ("BOAC", "Bank Of Africa Côte d'Ivoire", "Finance", 7100, 580, 8.17, "2026-05-05", "2026-05-20"),
        ("CABC", "Sicable Côte d'Ivoire", "Industrie", 1150, 95, 8.26, "2026-07-01", "2026-07-15"),
        ("ONTBF", "ONATEL Burkina Faso", "Services Publics", 2400, 210, 8.75, "2026-06-12", "2026-06-30"),
        ("SIVC", "Société Ivoirienne de Ciments", "Distribution", 800, 60, 7.50, "2026-05-15", "2026-05-30"),
        ("UNLC", "Unilever Côte d'Ivoire", "Distribution", 6500, 450, 6.92, "2026-06-18", "2026-07-02")
    ]

    for ticker, nom, secteur, cours, div, yield_pct, detach, paie in actions_data:
        cursor.execute("""
            INSERT OR REPLACE INTO actions (ticker, nom, secteur, cours_actuel, dernier_dividende_net, yield_net_pct, date_detachement, date_paiement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, nom, secteur, cours, div, yield_pct, detach, paie))

    conn.commit()
    conn.close()
    print("✅ Base de données alimentée avec succès !")

if __name__ == "__main__":
    injecter_donnees_brvm()