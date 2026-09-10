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


# Chargement des données
df_screening = charger_donnees_screening()

# --- BARRE LATÉRALE : FILTRES & CONFIGURATION ---
st.sidebar.title("🎛️ Panneau de Contrôle")

st.sidebar.header("🔍 Filtres du Screener")

# 1. Filtre Recherche Ticker
recherche_ticker = st.sidebar.text_input(
    "Rechercher un Ticker :", ""
).strip().upper()

# 2. Filtre Plage de Variation (%)
if not df_screening.empty and "Variation (%)" in df_screening.columns:
    min_var_val = float(df_screening["Variation (%)"].min())
    max_var_val = float(df_screening["Variation (%)"].max())
    if min_var_val < max_var_val:
        var_range = st.sidebar.slider(
            "Intervalle de Variation (%) :",
            min_value=min_var_val,
            max_value=max_var_val,
            value=(min_var_val, max_var_val),
            step=0.5,
        )
    else:
        var_range = (-10.0, 10.0)
else:
    var_range = (-100.0, 100.0)

# 3. Filtre Volume Minimum
if not df_screening.empty and "Volume" in df_screening.columns:
    min_volume = st.sidebar.number_input(
        "Volume minimum :", min_value=0, value=0, step=100
    )
else:
    min_volume = 0

st.sidebar.markdown("---")

# 4. Configuration des frais SGI
st.sidebar.header("⚙️ Configuration SGI")
taux_frais_sgi = (
    st.sidebar.slider(
        "Taux de frais SGI par transaction (%)",
        min_value=0.5,
        max_value=3.0,
        value=1.5,
        step=0.1,
        help="Frais de courtage SGI + redevances BRVM + TVA",
    )
    / 100
)

# --- APPLICATION DES FILTRES SUR LE SCREENING ---
df_filtre = df_screening.copy()
if not df_filtre.empty:
    if recherche_ticker:
        df_filtre = df_filtre[
            df_filtre["Ticker"].str.contains(
                recherche_ticker, case=False, na=False
            )
        ]
    if "Variation (%)" in df_filtre.columns:
        df_filtre = df_filtre[
            (df_filtre["Variation (%)"] >= var_range[0])
            & (df_filtre["Variation (%)"] <= var_range[1])
        ]
    if "Volume" in df_filtre.columns:
        df_filtre = df_filtre[df_filtre["Volume"] >= min_volume]

# --- CORPS PRINCIPAL ---
st.title("📊 BRVM Quantum Analytics")

if df_screening.empty:
    st.warning(
        "Aucune donnée disponible dans la base. Lancez le scraper pour alimenter `brvm.db`."
    )
else:
    tab1, tab2 = st.tabs(
        ["📈 Screener & Graphiques", "🧮 Simulateur d'Investissement (Nets SGI)"]
    )

    # --- ONGLET 1 : SCREENER & FILTRES ---
    with tab1:
        # KPI d'en-tête
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        nb_filtre = len(df_filtre)
        hausses = (
            len(df_filtre[df_filtre["Variation (%)"] > 0])
            if "Variation (%)" in df_filtre.columns
            else 0
        )
        baisses = (
            len(df_filtre[df_filtre["Variation (%)"] < 0])
            if "Variation (%)" in df_filtre.columns
            else 0
        )
        vol_total = (
            df_filtre["Volume"].sum()
            if "Volume" in df_filtre.columns
            else 0
        )

        kpi1.metric("Actions Sélectionnées", f"{nb_filtre} / {len(df_screening)}")
        kpi2.metric("Hausses 🚀", hausses)
        kpi3.metric("Baisses 🔻", baisses)
        kpi4.metric("Volume Filtré", f"{vol_total:,.0f}")

        st.markdown("---")
        st.subheader("Tableau du Marché (Filtré)")
        st.dataframe(df_filtre, use_container_width=True)

        st.markdown("---")
        st.subheader("Analyse Historique")
        tickers_disponibles = (
            df_filtre["Ticker"].unique()
            if not df_filtre.empty
            else df_screening["Ticker"].unique()
        )
        ticker_choisi = st.selectbox(
            "Sélectionnez une action pour afficher son cours :",
            tickers_disponibles,
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
            st.info("Aucun historique encore enregistré pour cette action.")

    # --- ONGLET 2 : SIMULATEUR SGI ---
    with tab2:
        st.subheader("Simulateur de Rendement Net (Frais SGI inclus)")

        col_input1, col_input2, col_input3 = st.columns(3)

        with col_input1:
            action_simu = st.selectbox(
                "Action à simuler :",
                df_screening["Ticker"].unique(),
                key="sim_ticker",
            )
            cours_actuel = (
                df_screening.loc[
                    df_screening["Ticker"] == action_simu, "Cours (FCFA)"
                ].values[0]
                if "Cours (FCFA)" in df_screening.columns
                else 1000
            )

        with col_input2:
            prix_achat = st.number_input(
                "Prix d'achat unitaire (FCFA)",
                value=float(cours_actuel),
                step=50.0,
            )
            quantite = st.number_input(
                "Nombre d'actions", value=100, min_value=1
            )

        with col_input3:
            prix_vente_cible = st.number_input(
                "Prix de revente estimé (FCFA)",
                value=float(round(cours_actuel * 1.1)),
                step=50.0,
            )

        # Calculs SGI
        capital_brut = quantite * prix_achat
        frais_achat = capital_brut * taux_frais_sgi
        cout_total_investi = capital_brut + frais_achat
        prix_revient_unitaire = cout_total_investi / quantite

        produit_brut_vente = quantite * prix_vente_cible
        frais_vente = produit_brut_vente * taux_frais_sgi
        produit_net_vente = produit_brut_vente - frais_vente

        total_frais_sgi = frais_achat + frais_vente
        gain_brut = produit_brut_vente - capital_brut
        gain_net = produit_net_vente - cout_total_investi
        rendement_net_pct = (
            (gain_net / cout_total_investi) * 100 if cout_total_investi > 0 else 0
        )
        prix_breakeven = prix_achat * (
            (1 + taux_frais_sgi) / (1 - taux_frais_sgi)
        )

        st.markdown("---")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Capital Inverti Total", f"{cout_total_investi:,.0f} FCFA")
        m2.metric("Total Frais SGI", f"{total_frais_sgi:,.0f} FCFA")
        m3.metric(
            "Gain Net Réel",
            f"{gain_net:,.0f} FCFA",
            delta=f"{rendement_net_pct:.2f}%",
        )
        m4.metric(
            "Seuil de Rentrabilité", f"{prix_breakeven:,.0f} FCFA"
        )

        st.markdown("**Synthèse financière de la transaction :**")
        st.write(
            f"* **Prix de revient net par action** : `{prix_revient_unitaire:,.2f} FCFA`"
        )
        st.write(
            f"* **Plus-value brute (hors frais)** : `{gain_brut:,.0f} FCFA`"
        )
        st.write(
            f"* **Hausse minimale requise pour breakeven** : `{((prix_breakeven/prix_achat)-1)*100:.2f}%`"
        )