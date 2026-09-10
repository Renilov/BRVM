import datetime
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import fundamentals

# --- CONFIGURATION PAGE STREAMLIT ---
st.set_page_config(
    page_title="BRVM Quantum Analytics", page_icon="📈", layout="wide"
)

DB_NAME = "brvm.db"


# --- INITIALISATION ET BDD SQLITE ---
def init_tables_sqlite():
    """Initialise les tables SQLite sans altérer les données existantes."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Table Portefeuille
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portefeuille (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            quantite INTEGER,
            prix_achat REAL,
            date_achat TEXT
        )
    """)

    # 2. Table Suivi Longitudinal avec Horodatage du Grade (Partie III, IV, V - MBC-METH-2026-07-001)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suivi_longitudinal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            semaine TEXT NOT NULL,
            date_enregistrement TEXT,
            score_fondamental REAL,
            grade_zone TEXT DEFAULT 'NE',
            date_grade TEXT,
            ratio_liquidite REAL,
            commentaire TEXT,
            UNIQUE(ticker, semaine) ON CONFLICT REPLACE
        )
    """)

    # Migration douce au cas où la colonne date_grade manquait
    try:
        cursor.execute(
            "ALTER TABLE suivi_longitudinal ADD COLUMN date_grade TEXT"
        )
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà

    conn.commit()
    conn.close()


def verifier_peremption_grade(grade, date_grade_str):
    """Applique la règle de péremption des 21 jours (3 semaines) - Partie III."""
    if not grade or grade == "NE":
        return "NE (Non Évalué)", "gray", False

    if not date_grade_str:
        return f"Grade {grade} (Date inconnue)", "orange", True

    try:
        date_g = datetime.datetime.strptime(
            date_grade_str, "%Y-%m-%d"
        ).date()
        jours_ecoules = (datetime.date.today() - date_g).days

        if jours_ecoules > 21:
            return (
                f"Grade {grade} ⚠️ Périmé ({jours_ecoules}j - À revalider)",
                "red",
                True,
            )
        else:
            return (
                f"Grade {grade} ✅ Valide ({jours_ecoules}j)",
                "green",
                False,
            )
    except Exception:
        return f"Grade {grade}", "blue", False


def charger_donnees_screening():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM screening", conn)
        conn.close()
        return df
    except Exception:
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


def enregistrer_suivi_semaine(
    ticker,
    semaine,
    score,
    grade="NE",
    date_grade=None,
    ratio_liq=None,
    commentaire="",
    date_eng=None,
):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    if date_eng is None:
        date_eng = today_str
    if date_grade is None or grade == "NE":
        date_grade = today_str if grade != "NE" else None

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO suivi_longitudinal 
        (ticker, semaine, date_enregistrement, score_fondamental, grade_zone, date_grade, ratio_liquidite, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, semaine) DO UPDATE SET
            date_enregistrement = excluded.date_enregistrement,
            score_fondamental = excluded.score_fondamental,
            grade_zone = excluded.grade_zone,
            date_grade = excluded.date_grade,
            ratio_liquidite = excluded.ratio_liquidite,
            commentaire = excluded.commentaire
    """,
        (
            ticker,
            semaine,
            date_eng,
            score,
            grade,
            date_grade,
            ratio_liq,
            commentaire,
        ),
    )
    conn.commit()
    conn.close()


def charger_suivi_longitudinal():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(
            "SELECT * FROM suivi_longitudinal ORDER BY ticker, semaine ASC",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def creer_jauge_concentration(titre, valeur, seuil, max_val=100):
    """Génère un graphique Plotly de jauge semi-circulaire pour le contrôle de risque."""
    est_depasse = valeur > seuil
    couleur_barre = "#FF2B2B" if est_depasse else "#00CC96"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(valeur, 1),
            number={"suffix": "%", "font": {"size": 24}},
            title={
                "text": f"<b>{titre}</b><br><span style='font-size:0.8em;color:gray'>Seuil Max : {seuil}%</span>",
                "font": {"size": 14},
            },
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": "gray",
                },
                "bar": {"color": couleur_barre},
                "bgcolor": "white",
                "borderwidth": 1,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, seuil], "color": "rgba(0, 204, 150, 0.15)"},
                    {
                        "range": [seuil, max_val],
                        "color": "rgba(255, 43, 43, 0.2)",
                    },
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": seuil,
                },
            },
        )
    )
    fig.update_layout(
        height=210,
        margin=dict(l=20, r=20, t=50, b=10),
        font={"family": "Arial"},
    )
    return fig


# Lancement DB
init_tables_sqlite()
df_screening = charger_donnees_screening()
financials_dict = fundamentals.charger_financials()


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


# --- EN-TÊTE PRINCIPAL ---
st.title("📊 BRVM Quantum Analytics")

if df_screening.empty:
    st.warning(
        "Aucune donnée dans la base. Exécutez `boc_scraper.py` pour alimenter le screener."
    )
else:
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📈 Screener & Graphiques",
            "🧮 Simulateur (Nets SGI)",
            "💼 Mon Portefeuille",
            "🔬 Analyse Fondamentale & Value",
        ]
    )

    # --- ONGLET 1 : SCREENER & HISTORIQUE ---
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
            "Historique du cours :",
            df_screening["Ticker"].unique(),
            key="s1_t",
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

    # --- ONGLET 2 : SIMULATEUR DE FRAIS SGI ---
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

    # --- ONGLET 3 : MON PORTEFEUILLE & CONTRÔLE DES RISQUES ---
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

            df_merged["Secteur"] = df_merged["ticker"].apply(
                lambda t: financials_dict.get(t, {}).get("Secteur", "Inconnu")
            )

            tot_investi = df_merged["Investissement Total"].sum()
            tot_valeur_nette = df_merged["Valeur Nette Estimation"].sum()
            tot_gain_net = tot_valeur_nette - tot_investi
            tot_perf_pct = (
                (tot_gain_net / tot_investi) * 100 if tot_investi > 0 else 0
            )

            kp1, kp2, kp3, kp4 = st.columns(4)
            kp1.metric("Capital Investi", f"{tot_investi:,.0f} FCFA")
            kp2.metric("Valeur Nette Total", f"{tot_valeur_nette:,.0f} FCFA")
            kp3.metric(
                "Gain Net FCFA",
                f"{tot_gain_net:,.0f} FCFA",
                delta=f"{tot_perf_pct:.2f}%",
            )
            kp4.metric("Lignes Ouvertes", len(df_merged))

            st.markdown("---")
            st.markdown("### 🛡️ Contrôle & Jauges de Risque (Partie X)")

            df_poids_ligne = (
                df_merged.groupby("ticker")["Valeur Nette Estimation"]
                .sum()
                .reset_index()
            )
            df_poids_ligne["Poids (%)"] = (
                df_poids_ligne["Valeur Nette Estimation"] / tot_valeur_nette
            ) * 100

            df_poids_secteur = (
                df_merged.groupby("Secteur")["Valeur Nette Estimation"]
                .sum()
                .reset_index()
            )
            df_poids_secteur["Poids (%)"] = (
                df_poids_secteur["Valeur Nette Estimation"] / tot_valeur_nette
            ) * 100

            max_ligne = df_poids_ligne.sort_values(
                "Poids (%)", ascending=False
            ).iloc[0]
            max_secteur = df_poids_secteur.sort_values(
                "Poids (%)", ascending=False
            ).iloc[0]

            jauge_col1, jauge_col2 = st.columns(2)

            with jauge_col1:
                fig_jauge_ligne = creer_jauge_concentration(
                    f"Ligne max ({max_ligne['ticker']})",
                    max_ligne["Poids (%)"],
                    seuil=15.0,
                )
                st.plotly_chart(fig_jauge_ligne, use_container_width=True)

                if max_ligne["Poids (%)"] > 15.0:
                    st.error(
                        f"🚨 **Dépassement Ligne** : **{max_ligne['ticker']}** fait **{max_ligne['Poids (%)']:.1f}%** du portefeuille (Seuil : 15%). Renforcement **BLOQUÉ**."
                    )
                else:
                    st.success(
                        f"✅ **Ligne Conforme** : **{max_ligne['ticker']}** à **{max_ligne['Poids (%)']:.1f}%** (≤ 15%)."
                    )

            with jauge_col2:
                fig_jauge_secteur = creer_jauge_concentration(
                    f"Secteur max ({max_secteur['Secteur']})",
                    max_secteur["Poids (%)"],
                    seuil=50.0,
                )
                st.plotly_chart(fig_jauge_secteur, use_container_width=True)

                if max_secteur["Poids (%)"] > 50.0:
                    st.error(
                        f"🚨 **Dépassement Secteur** : **{max_secteur['Secteur']}** fait **{max_secteur['Poids (%)']:.1f}%** du portefeuille (Seuil : 50%). Renforcement **BLOQUÉ**."
                    )
                else:
                    st.success(
                        f"✅ **Secteur Conforme** : **{max_secteur['Secteur']}** à **{max_secteur['Poids (%)']:.1f}%** (≤ 50%)."
                    )

            st.markdown("---")
            cols_show = [
                "id",
                "ticker",
                "Secteur",
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

            with st.expander("🗑️ Supprimer une ligne de position"):
                del_id = st.selectbox(
                    "Sélectionner l'ID à supprimer :", df_merged["id"].tolist()
                )
                if st.button("Confirmer la suppression"):
                    supprimer_position(del_id)
                    st.rerun()

    # --- ONGLET 4 : ANALYSE FONDAMENTALE & TRAÇABILITÉ DES GRADES ---
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
                f"Données fondamentales indisponibles dans `financials.json` pour **{ticker_fund}**."
            )
        else:
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
                st.markdown("### 💰 Dividende & Marge de Sécurité")
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

            # --- PARTIE V & III : TRAÇABILITÉ DES GRADES ET SUIVI LONGITUDINAL ---
            st.markdown("---")
            st.subheader(
                "📜 Traçabilité des Grades (Gate) & Suivi Longitudinal (Parties III, IV, V)"
            )

            # Récupération du dernier grade pour le titre sélectionné
            df_long = charger_suivi_longitudinal()
            grade_actuel_str = "NE (Non Évalué)"

            if not df_long.empty:
                df_t = df_long[df_long["ticker"] == ticker_fund]
                if not df_t.empty:
                    dernier_releve = df_t.sort_values("id").iloc[-1]
                    lbl, color, est_perime = verifier_peremption_grade(
                        dernier_releve.get("grade_zone"),
                        dernier_releve.get("date_grade"),
                    )
                    st.markdown(
                        f"#### **Statut Graphique Actuel** : `{lbl}` (Date d'obtention : `{dernier_releve.get('date_grade', 'N/A')}`)"
                    )
                    if est_perime:
                        st.warning(
                            "⚠️ **Règle de Péremption (Partie III)** : Ce grade a plus de 21 jours sans revalidation. Veuillez procéder à une nouvelle validation graphique avant toute décision."
                        )

            with st.expander(
                f"📝 Valider / Revalider le Grade et le Score de {ticker_fund}"
            ):
                col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
                with col_s1:
                    s_semaine = st.text_input(
                        "Identifiant Semaine / BOC",
                        value="S1",
                        key="s_sem",
                        help="Ex: S1, S2, ou BOC_168",
                    )
                with col_s2:
                    s_grade = st.selectbox(
                        "Grade de Zone (Gate)",
                        ["NE", "A", "B", "C"],
                        key="s_grd",
                        help="Partie III : Grade A (Taille pleine), B (Demi-taille), C (Tactique)",
                    )
                with col_s3:
                    s_date_grade = st.date_input(
                        "Date de Validation Graphique",
                        value=datetime.date.today(),
                        key="s_dt_g",
                        help="Date d'évaluation graphique (Horodatage)",
                    )
                with col_s4:
                    s_ratio = st.number_input(
                        "Ratio Liquidité",
                        value=0.0,
                        step=0.1,
                        key="s_rat",
                        help="Volume jour / Vente résiduelle",
                    )
                with col_s5:
                    s_comm = st.text_input(
                        "Commentaire / Alerte", value="RAS", key="s_com"
                    )

                if st.button("💾 Sauvegarder dans la table `suivi_longitudinal`"):
                    enregistrer_suivi_semaine(
                        ticker=ticker_fund,
                        semaine=s_semaine,
                        score=an["score_composite"],
                        grade=s_grade,
                        date_grade=str(s_date_grade)
                        if s_grade != "NE"
                        else None,
                        ratio_liq=s_ratio if s_ratio > 0 else None,
                        commentaire=s_comm,
                    )
                    st.success(
                        f"Horodatage et Grade de {ticker_fund} enregistrés pour {s_semaine} !"
                    )
                    st.rerun()

            # Affichage du tableau pivot cumulatif avec Horodatages
            if not df_long.empty:
                st.markdown("#### 📊 Évolution Multisemaines des Scores par Titre")

                df_pivot = df_long.pivot(
                    index="ticker",
                    columns="semaine",
                    values="score_fondamental",
                )

                # Récupération et formatage des derniers grades avec date
                df_last = df_long.sort_values("id").groupby("ticker").last()

                def format_grade_info(row):
                    lbl, _, _ = verifier_peremption_grade(
                        row.get("grade_zone"), row.get("date_grade")
                    )
                    return lbl

                df_pivot["Grade Actuel & Horodatage"] = df_last.apply(
                    format_grade_info, axis=1
                )
                df_pivot["Dernier Commentaire"] = df_last["commentaire"]

                st.dataframe(df_pivot, use_container_width=True)