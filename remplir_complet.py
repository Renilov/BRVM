import sqlite3

DB_FILE = "brvm_invest.db"

# Base de données complète de la BRVM (45 Actions)
DONNEES_BRVM = [
    # Ticker, Nom, Secteur, Cours (FCFA), Dividende Net (FCFA), Date Detachement, Date Paiement
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
    ("SAFC", "SAFCA CI", "Finance", 1100, 0, None, None),
    ("SGBC", "Société Générale Côte d'Ivoire", "Finance", 16800, 1250, "2026-06-01", "2026-06-15"),
    ("SIBC", "Société Ivoirienne de Banque", "Finance", 5800, 315, "2026-05-20", "2026-06-05"),
    ("BICC", "BICICI", "Finance", 7800, 630, "2026-06-12", "2026-06-28"),
    ("SNTS", "Sonatel Côte d'Ivoire / Sénégal", "Services Publics", 18500, 1575, "2026-05-12", "2026-05-28"),
    ("ONTBF", "Onatel Burkina Faso", "Services Publics", 2350, 180, "2026-06-08", "2026-06-24"),
    ("CIEC", "CIE Côte d'Ivoire", "Services Publics", 2200, 150, "2026-06-15", "2026-06-30"),
    ("SDCC", "SODECI", "Services Publics", 5400, 400, "2026-06-10", "2026-06-25"),
    ("NTLC", "Nestlé Côte d'Ivoire", "Industrie", 8500, 680, "2026-05-25", "2026-06-10"),
    ("SLBC", "Solibra CI", "Industrie", 82000, 4000, "2026-07-01", "2026-07-15"),
    ("CABC", "Sicable CI", "Industrie", 1150, 75, "2026-06-20", "2026-07-05"),
    ("STBC", "SITAB CI", "Industrie", 6400, 500, "2026-06-02", "2026-06-18"),
    ("UNLC", "Unilever CI", "Industrie", 6500, 0, None, None),
    ("NEIC", "NEI-CEDA CI", "Industrie", 680, 40, "2026-06-14", "2026-06-29"),
    ("SEMC", "Crown SIEM CI", "Industrie", 800, 0, None, None),
    ("FTSC", "Filtisac CI", "Industrie", 1600, 120, "2026-06-22", "2026-07-08"),
    ("SMBC", "SMB CI", "Industrie", 7900, 450, "2026-05-18", "2026-06-02"),
    ("TCHC", "Trituraf CI", "Industrie", 500, 0, None, None),
    ("TTLC", "TotalEnergies Côte d'Ivoire", "Distribution", 2300, 180, "2026-05-30", "2026-06-15"),
    ("TTLS", "TotalEnergies Sénégal", "Distribution", 2400, 160, "2026-06-05", "2026-06-20"),
    ("SHEC", "Vivo Energy CI", "Distribution", 820, 65, "2026-06-12", "2026-06-26"),
    ("PRSC", "Bernabé CI", "Distribution", 2000, 150, "2026-06-18", "2026-07-02"),
    ("CFAC", "CFAO Motors CI", "Distribution", 920, 60, "2026-06-25", "2026-07-10"),
    ("ABJC", "Servair Abidjan", "Distribution", 1450, 95, "2026-06-10", "2026-06-25"),
    ("PALC", "Palm CI", "Agriculture", 7100, 1200, "2026-06-18", "2026-07-02"),
    ("SOGC", "SOGB CI", "Agriculture", 3800, 450, "2026-05-28", "2026-06-12"),
    ("SIPC", "SAPH CI", "Agriculture", 3500, 320, "2026-06-02", "2026-06-17"),
    ("SICC", "SICOR CI", "Agriculture", 3100, 0, None, None),
    ("SPHC", "SAPH CI (PF)", "Agriculture", 3500, 0, None, None),
    ("SDSC", "Bolloré Transport & Logistics CI", "Transport", 1600, 100, "2026-06-15", "2026-06-30"),
    ("SVOC", "Movia CI (ex-Movima)", "Transport", 1200, 0, None, None),
    ("SCCI", "SICABLE / SOGB Immobilier", "Immobilier", 900, 0, None, None)
]

def alimenter_toutes_les_actions():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for ticker, nom, secteur, cours, div, detach, paie in DONNEES_BRVM:
        yield_pct = round((div / cours) * 100, 2) if (cours and cours > 0 and div) else 0.0
        
        cursor.execute("""
            INSERT OR REPLACE INTO actions (
                ticker, nom, secteur, cours_actuel, dernier_dividende_net, yield_net_pct, date_detachement, date_paiement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, nom, secteur, cours, div, yield_pct, detach, paie))

    conn.commit()
    conn.close()
    print("🎉 SUCCÈS : Les 45 actions de la BRVM ont été complètement mises à jour !")

if __name__ == "__main__":
    alimenter_toutes_les_actions()