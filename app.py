import datetime
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
import fundamentals

# Configuration Streamlit
st.set_page_config(
    page_title="BRVM Quantum Analytics", page_icon="📈", layout="wide"
)

DB_NAME = "brvm.db"


# --- BASE DE DONNÉES ---
def charger_donnees_screening():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM screening", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erreur de lecture de la base : {e}")
        return pd.DataFrame()


def charger_historique_ticker(ticker):
    try:
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT date, cours, volume FROM historique WHERE ticker = ? ORDER BY date ASC"
        df = pd.read_sql_query(query, conn, params=(ticker,))
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def init_table_portefeuille():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portefeuille (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            quantite INTEGER,
            prix_achat REAL,
            date_achat TEXT
        )
    """)
    conn.commit()
    conn.close()


def charger_portefeuille():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM portefeuille", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def ajouter_position(ticker, quantite, prix_achat, date_achat):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO portefeuille (ticker, quantite, prix_achat, date_achat)
        VALUES (?, ?, ?, ?)
    """,
        (ticker, quantite, prix_achat, date_achat),
    )
    conn.commit()
    conn.close()


def supprimer_position(position_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portefeuille WHERE id = ?", (position_id,))
    conn.commit()
    conn.close()


# Initialisations
init_table_portefeuille()
df_screening = charger_donnees_screening()

# --- BARRE LATÉRALE ---
st.sidebar.title("🎛️ Panneau de Contrôle")
st.sidebar.header("🔍 Filtres du Screener")

recherche_ticker = st.sidebar.text_input(
    "Rechercher un Ticker :", ""
).strip().upper()

if not df_screening.empty and "Variation (%)" in df_screening.columns:
    min_var_val = float(df_screening["Variation (%)"].min())
    max_var_val = float(df_screening["Variation (%)"].max())
    var_range = (
        st.sidebar.slider(
            "Intervalle Variation (%) :",
            min_value=min_var_val,
            max_value=max_var_val,
            value=(min_var_val, max_var_val),
            step=0.5,
        )
        if min_var_val < max_var_val
        else (-10.0, 10.0)
    )
else:
    var_range = (-100.0, 100.0)

min_volume = (
    st.sidebar.number_input(
        "Volume minimum :", min_value=0, value=0, step=100
    )
    if not df_screening.empty and "Volume" in df_screening.columns
    else 0
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuration SGI")
taux_frais_sgi = (
    st.sidebar.slider(
        "Taux de frais SGI par transaction (%)",
        min_value=0.5,
        max_value=3.0,
        value=1.5,
        step=0.1,
    )
    / 100
)

# Application des filtres
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
    st.warning("Aucune donnée. Exécutez `boc_scraper.py` pour alimenter la base.")
else:
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📈 Screener & Graphiques",
            "🧮 Simulateur (Nets SGI)",
            "💼 Mon Portefeuille",
            "🔬 Analyse Fondamentale & Value",
        ]
    )

    # --- ONGLET 1 : SCREENER ---
    with tab1:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Actions Sélectionnées", f"{len(df_filtre)} / {len(df_screening)}"
        )
        k2.metric(
            "Hausses 🚀",
            len(df_filtre[df_filtre["Variation (%)"] > 0])
            if "Variation (%)" in df_filtre.columns
            else 0,
        )
        k3.metric(
            "Baisses 🔻",
            len(df_filtre[df_filtre["Variation (%)"] < 0])
            if "Variation (%)" in df_filtre.columns
            else 0,
        )
        k4.metric(
            "Volume Filtré",
            f"{df_filtre['Volume'].sum():,.0f}"
            if "Volume" in df_filtre.columns
            else "0",
        )

        st.markdown("---")
        st.dataframe(df_filtre, use_container_width=True)

        st.markdown("---")
        ticker_choisi = st.selectbox(
            "Historique du cours :", df_screening["Ticker"].unique()
        )
        df_hist = charger_historique_ticker(ticker_choisi)
        if not df_hist.empty:
            fig = px.line(
                df_hist,
                x="date",
                y="cours",
                title=f"Évolution - {ticker_choisi}",
                markers=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- ONGLET 2 : SIMULATEUR SGI ---
    with tab2:
        st.subheader("Simulateur de Rendement Net SGI")
        c1, c2, c3 = st.columns(3)
        with c1:
            action_simu = st.selectbox(
                "Action :", df_screening["Ticker"].unique(), key="sim_t"
            )
            cours_actuel = df_screening.loc[
                df_screening["Ticker"] == action_simu, "Cours (FCFA)"
            ].values[0]
        with c2:
            prix_achat = st.number_input(
                "Prix Achat Unitaire (FCFA)",
                value=float(cours_actuel),
                step=50.0,
            )
            quantite = st.number_input("Quantité", value=100, min_value=1)
        with c3:
            prix_vente = st.number_input(
                "Prix Vente Estimé (FCFA)",
                value=float(round(cours_actuel * 1.1)),
                step=50.0,
            )

        capital_brut = quantite * prix_achat
        frais_achat = capital_brut * taux_frais_sgi
        cout_total = capital_brut + frais_achat

        prod_brut = quantite * prix_vente
        frais_vente = prod_brut * taux_frais_sgi
        prod_net = prod_brut - frais_vente

        gain_net = prod_net - cout_total
        roi_net = (gain_net / cout_total) * 100
        breakeven = prix_achat * ((1 + taux_frais_sgi) / (1 - taux_frais_sgi))

        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Capital Total Investi", f"{cout_total:,.0f} FCFA")
        m2.metric("Total Frais SGI", f"{(frais_achat + frais_vente):,.0f} FCFA")
        m3.metric("Gain Net", f"{gain_net:,.0f} FCFA", delta=f"{roi_net:.2f}%")
        m4.metric("Seuil Rentrabilité", f"{breakeven:,.0f} FCFA")

    # --- ONGLET 3 : PORTEFEUILLE ---
    with tab3:
        st.subheader("📌 Ajouter une Ligne d'Achat")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            p_ticker = st.selectbox(
                "Action :", df_screening["Ticker"].unique(), key="p_tick"
            )
            cours_ref = df_screening.loc[
                df_screening["Ticker"] == p_ticker, "Cours (FCFA)"
            ].values[0]
        with col_p2:
            p_qte = st.number_input(
                "Quantité :", min_value=1, value=50, key="p_q"
            )
        with col_p3:
            p_prix = st.number_input(
                "Prix d'Achat Unitaire (FCFA) :",
                value=float(cours_ref),
                step=50.0,
                key="p_pr",
            )
        with col_p4:
            p_date = st.date_input(
                "Date d'achat :", datetime.date.today(), key="p_d"
            )

        if st.button("➕ Ajouter au portefeuille"):
            ajouter_position(p_ticker, p_qte, p_prix, str(p_date))
            st.success(f"Position sur {p_ticker} ajoutée !")
            st.rerun()

        st.markdown("---")
        df_port = charger_portefeuille()

        if df_port.empty:
            st.info("Votre portefeuille est actuellement vide.")
        else:
            df_merged = df_port.merge(
                df_screening[["Ticker", "Cours (FCFA)"]],
                left_on="ticker",
                right_on="Ticker",
                how="left",
            )
            df_merged["Cours Actuel"] = df_merged["Cours (FCFA)"].fillna(
                df_merged["prix_achat"]
            )

            df_merged["Cout Achat Brut"] = (
                df_merged["quantite"] * df_merged["prix_achat"]
            )
            df_merged["Frais Achat"] = (
                df_merged["Cout Achat Brut"] * taux_frais_sgi
            )
            df_merged["Investissement Total"] = (
                df_merged["Cout Achat Brut"] + df_merged["Frais Achat"]
            )

            df_merged["Valeur Actuelle Brute"] = (
                df_merged["quantite"] * df_merged["Cours Actuel"]
            )
            df_merged["Frais Vente Est."] = (
                df_merged["Valeur Actuelle Brute"] * taux_frais_sgi
            )
            df_merged["Valeur Nette Estimation"] = (
                df_merged["Valeur Actuelle Brute"] - df_merged["Frais Vente Est."]
            )

            df_merged["Gain Net FCFA"] = (
                df_merged["Valeur Nette Estimation"]
                - df_merged["Investissement Total"]
            )
            df_merged["Performance Net (%)"] = (
                df_merged["Gain Net FCFA"] / df_merged["Investissement Total"]
            ) * 100

            tot_investi = df_merged["Investissement Total"].sum()
            tot_valeur_nette = df_merged["Valeur Nette Estimation"].sum()
            tot_gain_net = tot_valeur_nette - tot_investi
            tot_perf_pct = (
                (tot_gain_net / tot_investi) * 100 if tot_investi > 0 else 0
            )

            kp1, kp2, kp3, kp4 = st.columns(4)
            kp1.metric("Capital Investi", f"{tot_investi:,.0f} FCFA")
            kp2.metric("Valeur Nette", f"{tot_valeur_nette:,.0f} FCFA")
            kp3.metric(
                "Gain Net FCFA",
                f"{tot_gain_net:,.0f} FCFA",
                delta=f"{tot_perf_pct:.2f}%",
            )
            kp4.metric("Lignes", len(df_merged))

            st.markdown("---")
            cols_show = [
                "id",
                "ticker",
                "quantite",
                "prix_achat",
                "Cours Actuel",
                "Investissement Total",
                "Valeur Nette Estimation",
                "Gain Net FCFA",
                "Performance Net (%)",
            ]
            st.dataframe(
                df_merged[cols_show].style.format(
                    {
                        "prix_achat": "{:,.0f} FCFA",
                        "Cours Actuel": "{:,.0f} FCFA",
                        "Investissement Total": "{:,.0f} FCFA",
                        "Valeur Nette Estimation": "{:,.0f} FCFA",
                        "Gain Net FCFA": "{:,.0f} FCFA",
                        "Performance Net (%)": "{:+.2f}%",
                    }
                ),
                use_container_width=True,
            )

            with st.expander("🗑️ Supprimer une ligne"):
                del_id = st.selectbox(
                    "ID à supprimer :", df_merged["id"].tolist()
                )
                if st.button("Confirmer"):
                    supprimer_position(del_id)
                    st.rerun()

    # --- ONGLET 4 : ANALYSE FONDAMENTALE & VALUE ---
    with tab4:
        st.subheader("🔬 Analyse Fondamentale & Valuation (Graham / Value)")

        ticker_fund = st.selectbox(
            "Sélectionner une action à analyser :",
            df_screening["Ticker"].unique(),
            key="fund_select",
        )

        cours_f = (
            df_screening.loc[
                df_screening["Ticker"] == ticker_fund, "Cours (FCFA)"
            ].values[0]
            if not df_screening.empty
            else 0
        )

        an = fundamentals.analyser_valeur_et_fondamentaux(ticker_fund, cours_f)

        if an is None:
            st.info(
                f"Données fondamentales indisponibles pour **{ticker_fund}**."
            )
        else:
            # En-tête Métriques
            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("Score Fondamental", f"{an['score_composite']} / 100")
            fc2.metric("Rendement Dividende", f"{an['dividend_yield']} %")
            fc3.metric(
                "Nombre de Graham",
                f"{an['nombre_graham']:,.0f} FCFA",
                delta=f"{an['marge_securite_graham']:.1f}% Marge",
            )
            fc4.metric("Capitalisation", f"{an['capitalisation']:,.0f} FCFA")

            st.markdown("---")

            # Cartes d'Analyse Ratios
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                st.markdown("### 📊 Valorisation & Rentabilité")
                st.write(f"* **Nom de la Société** : `{an['nom']}`")
                st.write(f"* **Secteur d'Activité** : `{an['secteur']}`")
                st.write(
                    f"* **BPA (Bénéfice Par Action)** : `{an['bpa']:,.2f} FCFA`"
                )
                st.write(
                    f"* **VNC (Valeur Comptable)** : `{an['vnc']:,.2f} FCFA`"
                )
                st.write(f"* **P/E (Price to Earnings)** : `{an['pe_ratio']} x`")
                st.write(f"* **P/B (Price to Book)** : `{an['pb_ratio']} x`")
                st.write(f"* **ROE (Rentabilité FP)** : `{an['roe']} %`")

            with r_col2:
                st.markdown("### 💰 Dividende & Décote Graham")
                st.write(
                    f"* **Dividende par Action** : `{an['dividende']:,.2f} FCFA`"
                )
                st.write(
                    f"* **Ratio de Distribution (Payout)** : `{an['payout_ratio']} %`"
                )
                st.write(
                    f"* **Résultat Net Global Est.** : `{an['resultat_net_total']:,.0f} FCFA`"
                )
                st.write(
                    f"* **Capitaux Propres Totaux Est.** : `{an['capitaux_propres_totaux']:,.0f} FCFA`"
                )
                st.write(
                    f"* **Seuil Théorique de Graham** : `{an['nombre_graham']:,.0f} FCFA`"
                )

                if an["marge_securite_graham"] > 0:
                    st.success(
                        f"💡 **Décote de valeur** : L'action se négocie avec **{an['marge_securite_graham']:.1f}% de marge de sécurité** sous son prix de Graham."
                    )
                else:
                    st.warning(
                        f"⚠️ **Surcote relative** : Le cours actuel dépasse de **{abs(an['marge_securite_graham']):.1f}%** le Nombre de Graham."
                    )