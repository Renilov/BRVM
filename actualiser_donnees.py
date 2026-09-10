import sqlite3

DB_FILE = "brvm_invest.db"

def mettre_a_jour_base():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Données réelles / réalistes de la BRVM (Ticker, Nom, Secteur, Cours, Dividende Net, Date Détachement, Date Paiement)
    donnees_brvm = [
        ("BOAB", "Bank of Africa Bénin", "Finance", 6800, 610, "2026-05-10", "2026-05-25"),
        ("BOBF", "Bank of Africa Burkina Faso", "Finance", 6250, 580, "2026-05-15", "2026-05-30"),
        ("BOCI", "Bank of Africa Côte d'Ivoire", "Finance", 7500, 700, "2026-05-02", "2026-05-18"),
        ("BOAM", "Bank of Africa Mali", "Finance", 2100, 270, "2026-06-01", "2026-06-15"),
        ("BOAN", "Bank of Africa Niger", "Finance", 5900, 530, "2026-05-20", "2026-06-04"),
        ("BOAS", "Bank of Africa Sénégal", "Finance", 3200, 170, "2026-06-10", "2026-06-25"),
        ("CBIB", "Coris Bank International", "Finance", 10200, 540, "2026-05-08", "2026-05-22"),
        ("ETIT", "Ecobank Transnational Inc.", "Finance", 19, 1.8, "2026-05-28", "2026-06-12"),
        ("NSBC", "NSIA Banque Côte d'Ivoire", "Finance", 6100, 500, "2026-06-05", "2026-06-20"),
        ("ORGT", "Oragroup Togo", "Finance", 2400, 150, "2026-06-15", "2026-06-30"),
        ("SGBC", "Société Générale Côte d'Ivoire", "Finance", 17500, 1250, "2026-05-12", "2026-05-27"),
        ("SNTS", "Sonatel Sénégal", "Services Publics", 18900, 1575, "2026-05-14", "2026-05-29"),
        ("PALC", "Palm Côte d'Ivoire", "Agriculture", 7100, 800, "2026-06-18", "2026-07-02"),
        ("ONTBF", "ONATEL Burkina Faso", "Services Publics", 2350, 210, "2026-06-08", "2026-06-24")
    ]

    for ticker, nom, secteur, cours, div, detach, paie in donnees_brvm:
        # Calcul automatique du rendement net en %
        yield_pct = round((div / cours) * 100, 2) if cours > 0 else 0.0

        cursor.execute("""
            INSERT OR REPLACE INTO actions (
                ticker, nom, secteur, cours_actuel, dernier_dividende_net, yield_net_pct, date_detachement, date_paiement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, nom, secteur, cours, div, yield_pct, detach, paie))

    conn.commit()
    conn.close()
    print("✅ Mise à jour réussie : Les cours, dividendes, rendements (Yield %) et dates sont enregistrés !")

if __name__ == "__main__":
    mettre_a_jour_base()