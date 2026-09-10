import os
import glob
import sqlite3
import pandas as pd
import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(
    page_title="BRVM Investment Dashboard — Institutional Quantum",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 BRVM Investment Dashboard — Institutional Quantum")
st.caption("Suivi des cours réels, calendrier des dividendes (détachement & paiement), optimisation Markowitz & Risk Analytics.")

# ==============================================================================
# CHARGEMENT DES DONNÉES DEPUIS LA BASE SQL DE SCRAPER.PY
# ==============================================================================
@st.cache_data(ttl=10)
def charger_donnees_reelles():
    df = pd.DataFrame()

    # 1. Recherche de bases de données SQLite (.db) créées par scraper.py
    fichiers_db = glob.glob("*.db") + glob.glob("data/*.db") + glob.glob("*.sqlite")
    
    for db_path in fichiers_db:
        try:
            conn = sqlite3.connect(db_path)
            # Récupération de la liste des tables
            tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)['name'].tolist()
            
            # Parcours des tables probables
            for table in ['cours', 'actions', 'quotes', 'market_data', 'dividendes', 'brvm_latest']:
                if table in tables:
                    df_temp = pd.read_sql(f"SELECT * FROM {table}", conn)
                    if not df_temp.empty:
                        df = df_temp
                        st.toast(f"✅ Données SQL chargées depuis `{db_path}` (table `{table}`)", icon="🗄️")
                        break
            
            # Si aucune table spécifique, on prend la première table disponible
            if df.empty and tables:
                df = pd.read_sql(f"SELECT * FROM {tables[0]}", conn)
                st.toast(f"✅ Données SQL chargées depuis `{db_path}`", icon="🗄️")
                
            conn.close()
            if not df.empty:
                return normaliser_dataframe(df)
        except Exception:
            pass

    # 2. Secours : Recherche dans les fichiers JSON
    fichiers_json = ["data/brvm_latest.json", "brvm_latest.json", "data/brvm_market.json"]
    for jf in fichiers_json:
        if os.path.exists(jf):
            try:
                df = pd.read_json(jf)
                if not df.empty:
                    st.toast(f"✅ Données chargées depuis `{jf}`", icon="📄")
                    return normaliser_dataframe(df)
            except Exception:
                pass

    return pd.DataFrame()

def normaliser_dataframe(df):
    cols_map = {}
    for col in df.columns:
        c = str(col).strip().upper()
        if any(k in c for k in ['TICKER', 'VALEUR', 'SYMBOLE', 'ACTION', 'SOCIETE', 'CODE']):
            cols_map[col] = 'Ticker'
        elif any(k in c for k in ['COURS', 'DERNIER', 'PRIX', 'FERMETURE', 'CLOSE']):
            cols_map[col] = 'Cours (FCFA)'
        elif 'RSI' in c:
            cols_map[col] = 'RSI'
        elif any(k in c for k in ['VAR', 'CHANGE', 'VARIATION']):
            cols_map[col] = 'Variation (%)'
        elif any(k in c for k in ['DIVIDENDE', 'DIV_NET', 'NET']):
            cols_map[col] = 'Dividende Net'
        elif any(k in c for k in ['PER', 'P_E']):
            cols_map[col] = 'PER (x)'
        elif any(k in c for k in ['RENDEMENT', 'YIELD']):
            cols_map[col] = 'Rendement (%)'

    df = df.rename(columns=cols_map)

    # Nettoyage et formatage numérique
    if 'Cours (FCFA)' in df.columns:
        df['Cours (FCFA)'] = df['Cours (FCFA)'].astype(str).str.replace(' ', '').str.replace(',', '.').str.replace('FCFA', '')
        df['Cours (FCFA)'] = pd.to_numeric(df['Cours (FCFA)'], errors='coerce').fillna(0).astype(int)

    if 'Variation (%)' in df.columns:
        df['Variation (%)'] = df['Variation (%)'].astype(str).str.replace(' ', '').str.replace(',', '.').str.replace('%', '')
        df['Variation (%)'] = pd.to_numeric(df['Variation (%)'], errors='coerce').fillna(0.0)

    return df

# Chargement des données
df_marche = charger_donnees_reelles()

# Navigation par Onglets
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Screening & Calendrier Dividendes",
    "📊 Backtesting Réaliste (SGI)",
    "📈 Analyse Technique & Signaux",
    "💼 Portefeuille, CVaR & Liquidité"
])

# ------------------------------------------------------------------------------
# ONGLET 1 : SCREENING & COURS RÉELS
# ------------------------------------------------------------------------------
with tab1:
    st.subheader("🔍 Screening, Fondamentaux & Calendrier des Dividendes")

    if df_marche.empty:
        st.error("⚠️ Impossible de lire les données. Assurez-vous que le fichier `.db` est présent dans le dossier.")
    else:
        for col_name in ['PER (x)', 'Rendement (%)', 'Dividende Net', 'Détachement Coupon', 'Paiement Effectif']:
            if col_name not in df_marche.columns:
                df_marche[col_name] = "À préciser" if "Détachement" in col_name or "Paiement" in col_name or "Dividende" in col_name else "—"

        cols_ordre = ['Ticker', 'Cours (FCFA)', 'Variation (%)', 'PER (x)', 'Rendement (%)', 'Dividende Net', 'Détachement Coupon', 'Paiement Effectif']
        cols_presentes = [c for c in cols_ordre if c in df_marche.columns]

        st.dataframe(
            df_marche[cols_presentes],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Cours (FCFA)": st.column_config.NumberColumn(format="%d FCFA"),
                "Variation (%)": st.column_config.NumberColumn(format="%.2f %%"),
            }
        )

# ------------------------------------------------------------------------------
# ONGLET 2 : BACKTESTING
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📊 Backtesting Réaliste (SGI)")
    st.info("Simulation d'exécution d'ordres sur cours réels.")

# ------------------------------------------------------------------------------
# ONGLET 3 : ANALYSE TECHNIQUE
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("📈 Analyse Technique & Signaux")
    if not df_marche.empty and 'RSI' in df_marche.columns:
        st.dataframe(df_marche[['Ticker', 'Cours (FCFA)', 'RSI']], use_container_width=True, hide_index=True)
    else:
        st.info("Module d'indicateurs techniques prêt.")

# ------------------------------------------------------------------------------
# ONGLET 4 : PORTEFEUILLE & RISQUE
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("💼 Portefeuille, CVaR & Liquidité")
    st.info("Optimisation de portefeuille (Markowitz, VaR/CVaR).")