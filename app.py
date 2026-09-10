import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

# Configuration de la page Streamlit
st.set_page_config(
    page_title="BRVM Quantum Analytics", page_icon="📈", layout="wide"
)

DB_NAME = "brvm.db"


def charger_donnees_screening():
    """Charge les données actuelles depuis SQLite."""
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM screening", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erreur de lecture de la base de données : {e}")
        return pd.DataFrame()


def charger_historique_ticker(ticker):
    """Charge l'historique d'un titre spécifique."""
    try:
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT date, cours, volume FROM historique WHERE ticker = ? ORDER BY date ASC"
        df = pd.read_sql_query(query, conn, params=(ticker,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


# --- BARRE LATÉRALE (PARAMÈTRES SGI) ---
st.sidebar.header("⚙️ Configuration SGI")
taux_frais_sgi = (
    st.sidebar.slider(
        "Taux de frais SGI par transaction (%)",
        min_value=0.5,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="Inclut la commission SGI + redevance BRVM + TVA (généralement entre 1.2% et 1.8%)",
    )
    / 100
)

st.title("📊 BRVM Quantum Analytics")

# Chargement des données
df_screening = charger_donnees_screening()

if df_screening.empty:
    st.warning(
        "Aucune donnée disponible. Lancez d'abord le scraper pour alimenter la base."
    )
else:
    # Onglets principaux
    tab1, tab2 = st.tabs(
        ["📈 Screener & Graphiques", "🧮 Simulateur d'Investissement (Nets SGI)"]
    )

    # --- ONGLET 1 : SCREENER ---
    with tab1:
        st.subheader("Marché en Temps Réel / Clôture")
        st.dataframe(df_screening, use_container_width=True)

        st.subheader("Analyse Historique d'une Action")
        ticker_choisi = st.selectbox(
            "Sélectionnez une action :", df_screening["Ticker"].unique()
        )

        df_hist = charger_historique_ticker(ticker_choisi)
        if not df_hist.empty:
            fig = px.line(
                df_hist,
                x="date",
                y="cours",
                title=f"Évolution du cours - {ticker_choisi}",
                labels={"date": "Date", "cours": "Cours (FCFA)"},
                markers=True,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas encore d'historique disponible pour ce titre.")

    # --- ONGLET 2 : SIMULATEUR AVEC FRAIS SGI ---
    with tab2:
        st.subheader("Simulateur de Plus-Value avec Frais de Courtage")

        col_input1, col_input2, col_input3 = st.columns(3)

        with col_input1:
            action_simu = st.selectbox(
                "Action à simuler :",
                df_screening["Ticker"].unique(),
                key="sim_ticker",
            )
            # Récupération du cours actuel comme référence
            cours_actuel = df_screening.loc[
                df_screening["Ticker"] == action_simu, "Cours (FCFA)"
            ].values[0]

        with col_input2:
            prix_achat = st.number_input(
                "Prix d'achat par action (FCFA)",
                value=float(cours_actuel),
                step=50.0,
            )
            quantite = st.number_input(
                "Nombre d'actions achetées", value=100, min_value=1
            )

        with col_input3:
            prix_vente_cible = st.number_input(
                "Prix de revente estimé (FCFA)",
                value=float(round(cours_actuel * 1.1)),
                step=50.0,
            )

        # --- CALCULS FINANCIERS SGI ---
        # 1. Achat
        capital_brut = quantite * prix_achat
        frais_achat = capital_brut * taux_frais_sgi
        cout_total_investi = capital_brut + frais_achat
        prix_revient_unitaire = cout_total_investi / quantite

        # 2. Vente
        produit_brut_vente = quantite * prix_vente_cible
        frais_vente = produit_brut_vente * taux_frais_sgi
        produit_net_vente = produit_brut_vente - frais_vente

        # 3. Résultat
        total_frais_sgi = frais_achat + frais_vente
        gain_brut = produit_brut_vente - capital_brut
        gain_net = produit_net_vente - cout_total_investi
        rendement_net_pct = (
            (gain_net / cout_total_investi) * 100 if cout_total_investi > 0 else 0
        )

        # Prix d'équilibre (Breakeven) : Prix minimum de revente pour 0 FCFA de perte
        prix_breakeven = prix_achat * (
            (1 + taux_frais_sgi) / (1 - taux_frais_sgi)
        )

        st.markdown("---")

        # Affichage des métriques clés
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Capital Inverti Total", f"{cout_total_investi:,.0f} FCFA")
        m2.metric("Total Frais SGI (Achat+Vente)", f"{total_frais_sgi:,.0f} FCFA")
        m3.metric(
            "Gain Net Réel",
            f"{gain_net:,.0f} FCFA",
            delta=f"{rendement_net_pct:.2f}%",
        )
        m4.metric(
            "Prix de Seuil de Rentrabilité", f"{prix_breakeven:,.0f} FCFA"
        )

        # Détail synthétique de l'opération
        st.markdown("**Détail de l'Opération :**")
        st.write(
            f"* **Prix de revient par action (frais inclus)** : `{prix_revient_unitaire:,.2f} FCFA`"
        )
        st.write(
            f"* **Plus-value brute (hors frais)** : `{gain_brut:,.0f} FCFA`"
        )
        st.write(
            f"* **Prix minimum de revente sans perte** : `{prix_breakeven:,.2f} FCFA` (il faut une hausse minimale de `{((prix_breakeven/prix_achat)-1)*100:.2f}%` pour couvrir la SGI)."
        )