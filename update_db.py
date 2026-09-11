import datetime
import re
import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup

DB_NAME = "brvm.db"

# Headers HTTP pour simuler un navigateur standard
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def nettoyer_nombre(valeur):
    """Nettoie une chaîne texte pour la convertir en nombre (flottant ou entier)."""
    if pd.isna(valeur) or valeur is None:
        return 0.0
    val_str = str(valeur).replace(" ", "").replace("\xa0", "").replace(",", ".")
    val_str = re.sub(r"[^\d.-]", "", val_str)
    try:
        return float(val_str)
    except ValueError:
        return 0.0


def recuperer_cours_brvm():
    """
    Récupère la liste des cours des actions BRVM depuis le portail financier.
    Renvoie un DataFrame Pandas prêt pour la base de données.
    """
    url = "https://www.sikafinance.com/marches/cotation_brvm"
    print(f"🌐 Connexion à {url}...")

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # Lecture automatique des tableaux HTML présent sur la page
        tables = pd.read_html(response.text)

        if not tables:
            print("❌ Aucun tableau trouvé sur la page.")
            return pd.DataFrame()

        # Le premier grand tableau contient généralement les cotations
        df_brvm = tables[0]

        # Normalisation des noms de colonnes
        df_brvm.columns = [c.strip() for c in df_brvm.columns]

        # Adaptation selon la structure de la page Sika Finance
        # On cherche les colonnes clés : Valeur/Nom, Cours, Var, Vol
        col_nom = [c for c in df_brvm.columns if "Valeur" in c or "Action" in c or "Nom" in c]
        col_cours = [c for c in df_brvm.columns if "Cours" in c or "Dernier" in c]
        col_var = [c for c in df_brvm.columns if "Var" in c or "%" in c]
        col_vol = [c for c in df_brvm.columns if "Vol" in c]

        if not (col_nom and col_cours):
            print("⚠️ Structure du tableau différente de celle attendue.")
            return pd.DataFrame()

        donnees_nettoyees = []
        date_aujourdhui = datetime.date.today().strftime("%Y-%m-%d")

        for _, row in df_brvm.iterrows():
            nom_brut = str(row[col_nom[0]]).strip()

            # Extraction du symbole/ticker (ex: 'SNTS' ou le début du nom)
            # Sika affiche souvent 'SONATEL CI (SNTS)' ou juste le symbole
            ticker_match = re.search(r"\(([A-Z0-9]+)\)", nom_brut)
            ticker = ticker_match.group(1) if ticker_match else nom_brut[:4].upper()

            cours = nettoyer_nombre(row[col_cours[0]])
            variation = nettoyer_nombre(row[col_var[0]]) if col_var else 0.0
            volume = int(nettoyer_nombre(row[col_vol[0]])) if col_vol else 0

            # Filtre pour ignorer les lignes vides ou de sous-titres
            if cours > 0:
                donnees_nettoyees.append({
                    "Ticker": ticker,
                    "Nom": nom_brut,
                    "Cours (FCFA)": cours,
                    "Variation (%)": variation,
                    "Volume": volume,
                    "date_maj": date_aujourdhui,
                })

        df_final = pd.DataFrame(donnees_nettoyees)
        print(f"✅ {len(df_final)} actions BRVM récupérées avec succès.")
        return df_final

    except Exception as e:
        print(f"❌ Erreur lors de la récupération : {e}")
        return pd.DataFrame()


def mettre_a_jour_sqlite(df_screening):
    """
    Sauvegarde les cours dans les tables SQLite 'screening' et 'historique'.
    """
    if df_screening.empty:
        print("⚠️ Aucune donnée à enregistrer.")
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Mise à jour de la table screening (remplacement complet)
    df_screening.to_sql("screening", conn, if_exists="replace", index=False)
    print("💾 Table 'screening' mise à jour.")

    # 2. Ajout de la journée dans la table historique
    date_jour = df_screening["date_maj"].iloc[0]
    count_hist = 0

    for _, row in df_screening.iterrows():
        try:
            cursor.execute(
                """
                INSERT INTO historique (ticker, date, cours, volume)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    cours = excluded.cours,
                    volume = excluded.volume
                """,
                (row["Ticker"], date_jour, row["Cours (FCFA)"], int(row["Volume"])),
            )
            count_hist += 1
        except Exception as err:
            print(f"Erreur d'insertion historique pour {row['Ticker']}: {err}")

    conn.commit()
    conn.close()
    print(f"📈 {count_hist} enregistrements ajoutés à l'historique pour le {date_jour}.")


if __name__ == "__main__":
    print("🚀 Démarrage du script d'actualisation BRVM...")
    df_nouveaux_cours = recuperer_cours_brvm()
    if not df_nouveaux_cours.empty:
        mettre_a_jour_sqlite(df_nouveaux_cours)
        print("🎉 Actualisation terminée avec succès !")
    else:
        print("❌ Impossible de mettre à jour la base de données.")