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


# --- INITIALISATION BDD SQLITE ---
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

    # 2. Table Suivi Longitudinal (Parties III, IV, V - MBC-METH-2026-07-001)
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

    # 3. Table Signaux Contrarians (Partie VII - MBC-METH-2026-07-001)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signaux_contrarians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            semaine TEXT NOT NULL,
            date_signal TEXT,
            archetype TEXT NOT NULL,
            conviction TEXT,
            element_ignore TEXT,
            risque_principal TEXT,
            evolution TEXT,
            verdict TEXT DEFAULT 'EN COURS',
            UNIQUE(ticker, semaine, archetype) ON CONFLICT REPLACE
        )
    """)

    # Migration douce si la colonne date_grade manquait
    try:
        cursor.execute(
            "ALTER TABLE suivi_longitudinal ADD COLUMN date_grade TEXT"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()

    # Alimentation initiale pour la démo si la table signaux_contrarians est vide
    cursor.execute("SELECT COUNT(*) FROM signaux_contrarians")
    if cursor.fetchone()[0] == 0:
        exemples_signaux = [
            (
                "NTLC",
                "BOC N°162 (28/08)",
                "2026-08-28",
                "Archétype 1 — Sur-réaction négative",
                "MOYENNE",
                "Sur-réaction à -5,92 % avec dividende intact",
                "Risque de vente résiduelle à court terme",
                "Retournement net : +2,21 % le 04/09, catalyseur ex-dividende à J-3",
                "VALIDÉ",
            ),
            (
                "TTLC",
                "BOC N°162 (28/08)",
                "2026-08-28",
                "Archétype 2 — Catalyseur négligé",
                "MOYENNE",
                "Catalyseur négligé à J-3 (dividende)",
                "Marché passif jusqu'au détachement",
                "Dividende détaché le 31/08 ; réaction modeste (+0,60 %)",
                "NEUTRE",
            ),
            (
                "BOAC",
                "BOC N°162 (28/08)",
                "2026-08-28",
                "Archétype 3 — Dérating prolongé",
                "FAIBLE",
                "Dérating prolongé (PER 14.07)",
                "Carnet très vendeur (1 achat / 100 vente)",
                "Prix stabilisé (0,00 %) mais carnet toujours très vendeur",
                "EN COURS",
            ),
            (
                "NEIC",
                "BOC N°162 (28/08)",
                "2026-08-28",
                "Archétype 4 — Momentum sous-estimé",
                "FAIBLE",
                "Momentum sous-estimé",
                "Mur vendeur résiduel",
                "Mur vendeur augmenté de 900 à 4 192 titres — risque aggravé",
                "RISQUE CONFIRMÉ",
            ),
            (
                "ABJC",
                "BOC N°167 (04/09)",
                "2026-09-04",
                "Archétype 1 — Sur-réaction négative",
                "MOYENNE",
                "Repli de -1,27 % malgré dividende de 229 FCFA (J-26, ~5,9 %)",
                "Carnet à l'équilibre (116 achat / 149 vente)",
                "À surveiller à l'approche de l'échéance",
                "EN COURS",
            ),
            (
                "SMBC",
                "BOC N°167 (04/09)",
                "2026-09-04",
                "Archétype 2 — Catalyseur négligé",
                "MOYENNE-FORTE",
                "Dividende de 800 FCFA (~4,6 %) à J-14 à peine intégré (+1,16 %)",
                "Marché passif jusqu'au dernier moment",
                "Score 8/10, carnet fortement acheteur (40/5). Candidat prioritaire",
                "EN COURS",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO signaux_contrarians 
            (ticker, semaine, date_signal, archetype, conviction, element_ignore, risque_principal, evolution, verdict)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            exemples_signaux,
        )
        conn.commit()

    conn.close()


# --- FONCTIONS UTILITES ---
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
        if not df.empty:
            return df
    except Exception:
        pass

    data_defaut = [
        {
            "Ticker": "NTLC",
            "Nom": "NESTLE CI",
            "Cours (FCFA)": 7200,
            "Variation (%)": 2.21,
            "Volume": 3450,
        },
        {
            "Ticker": "ABJC",
            "Nom": "SERVAIR ABIDJAN",
            "Cours (FCFA)": 3880,
            "Variation (%)": -1.27,
            "Volume": 1200,
        },
        {
            "Ticker": "SMBC",
            "Nom": "SMB CI",
            "Cours (FCFA)": 17400,
            "Variation (%)": 1.16,
            "Volume": 5800,
        },
        {
            "Ticker": "BOAC",
            "Nom": "BANK OF AFRICA CI",
            "Cours (FCFA)": 6900,
            "Variation (%)": 0.00,
            "Volume": 890,
        },
        {
            "Ticker": "NEIC",
            "Nom": "NEI-CEDA CI",
            "Cours (FCFA)": 650,
            "Variation (%)": 0.00,
            "Volume": 4192,
        },
        {
            "Ticker": "TTLC",
            "Nom": "TOTALENERGIES CI",
            "Cours (FCFA)": 2350,
            "Variation (%)": 0.60,
            "Volume": 2100,
        },
        {
            "Ticker": "SGBC",
            "Nom": "SOCIETE GENERALE CI",
            "Cours (FCFA)": 18200,
            "Variation (%)": -0.82,
            "Volume": 4100,
        },
        {
            "Ticker": "SNTS",
            "Nom": "SONATEL SENEGAL",
            "Cours (FCFA)": 19500,
            "Variation (%)": 1.56,
            "Volume": 12500,
        },
    ]
    return pd.DataFrame(data_defaut)


def charger_historique_ticker(ticker):
    try:
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT date, cours, volume FROM historique WHERE ticker = ? ORDER BY date ASC"
        df = pd.read_sql_query(query, conn, params=(ticker,))
        conn.close()
        if not df.empty:
            return df
    except Exception:
        pass

    dates = pd.date_range(end=datetime.date.today(), periods=10).strftime(
        "%Y-%m-%d"
    )
    return pd.DataFrame({
        "date": dates,
        "cours": [7000, 7050, 6980, 6900, 7100, 7050, 7120, 7150, 7100, 7200],
        "volume": [1000, 1500, 800, 1200, 3000, 2100, 1800, 2500, 3100, 3450],
    })


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


# --- FONCTIONS SIGNAUX CONTRARIANS (PARTIE VII) ---
def charger_signaux_contrarians():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(
            "SELECT * FROM signaux_contrarians ORDER BY date_signal DESC, ticker ASC",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def enregistrer_signal_contrarian(
    ticker,
    semaine,
    archetype,
    conviction,
    element_ignore,
    risque_principal,
    evolution="",
    verdict="EN COURS",
    date_signal=None,
):
    if date_signal is None:
        date_signal = datetime.date.today().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO signaux_contrarians 
        (ticker, semaine, date_signal, archetype, conviction, element_ignore, risque_principal, evolution, verdict)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, semaine, archetype) DO UPDATE SET
            date_signal = excluded.date_signal,
            conviction = excluded.conviction,
            element_ignore = excluded.element_ignore,
            risque_principal = excluded.risque_principal,
            evolution = excluded.evolution,
            verdict = excluded.verdict
    """,
        (
            ticker,
            semaine,
            date_signal,
            archetype,
            conviction,
            element_ignore,
            risque_principal,
            evolution,
            verdict,
        ),
    )
    conn.commit()
    conn.close()


def supprimer_signal_contrarian(signal_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM signaux_contrarians WHERE id = ?", (signal_id,)
    )
    conn.commit()
    conn.close()


def detecter_signaux_contrarians_auto(df_screening, financials_dict):
    """Analyse automatique de la cote BRVM selon la Partie VII (MBC-METH-2026-07-001)."""
    signaux = []

    for _, row in df_screening.iterrows():
        ticker = row.get("Ticker")
        cours = float(row.get("Cours (FCFA)", 0))
        var = float(row.get("Variation (%)", 0))
        volume = float(row.get("Volume", 0))

        fin = financials_dict.get(ticker, {})
        div = float(fin.get("Dividende", 0))
        pe = float(fin.get("PER", 0))

        rendement_div = (div / cours * 100) if cours > 0 else 0

        # Archétype 1 : Sur-réaction négative
        if var <= -1.0 and rendement_div >= 4.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 1 — Sur-réaction négative",
                "Élément ignoré par le marché": f"Repli de {var:.2f} % alors que le rendement du dividende ({rendement_div:.1f} %) est intact.",
                "Risque principal": "Pression vendeuse résiduelle dans le carnet d'ordres à court terme.",
                "Conviction": "MOYENNE",
            })

        # Archétype 2 : Catalyseur négligé
        elif rendement_div >= 4.0 and -1.0 < var < 1.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 2 — Catalyseur négligé",
                "Élément ignoré par le marché": f"Dividende de {div:,.0f} FCFA ({rendement_div:.1f} %) proche, à peine intégré par le cours ({var:+.2f} %).",
                "Risque principal": "Le marché pourrait ignorer le catalyseur jusqu'au détachement.",
                "Conviction": "MOYENNE-FORTE",
            })

        # Archétype 3 : Dérating prolongé
        elif 0 < pe < 12.0 and -0.5 <= var <= 0.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 3 — Dérating prolongé",
                "Élément ignoré par le marché": f"PER bas ({pe:.2f}x) sous la moyenne secteur avec prix stabilisé ({var:+.2f} %).",
                "Risque principal": "Carnet toujours dominé par les vendeurs ; stabilisation non confirmée.",
                "Conviction": "FAIBLE",
            })

        # Archétype 4 : Momentum sous-estimé
        elif var >= 2.0 and volume > 3000:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 4 — Momentum sous-estimé",
                "Élément ignoré par le marché": f"Hausse marquée de {var:+.2f} % avec un volume important ({volume:,.0f} titres).",
                "Risque principal": "Risque d'un mur vendeur résiduel en haut de carnet.",
                "Conviction": "FAIBLE",
            })

    return pd.DataFrame(signaux)


def creer_jauge_concentration(titre, valeur, seuil, max_val=100):
    """Génère une jauge Plotly semi-circulaire pour le contrôle du risque."""
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


# --- DEMARRAGE BASE DE DONNEES ET DONNEES ---
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

# Filtres appliqués
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


# --- EN-TÊTE ET ONGLETS PRINCIPAUX ---
st.title("📊 BRVM Quantum Analytics")

with st.expander(
    "ℹ️ Résumé de la Méthodologie & Cadre de Décision (MBC-METH-2026-07-001)"
):
    st.markdown("""
    **BRVM Quantum Analytics** applique une discipline stricte en 5 piliers non négociables :
    1. **Valuation Value & Graham (Partie IV)** : Sélection des titres présentant un score fondamental élevé et une marge de sécurité via le Nombre de Graham.
    2. **Traçabilité des Grades / Gate (Partie III)** : Attribution d'un Grade de Zone ($A, B, C, NE$) horodaté avec **règle de péremption stricte à 21 jours**.
    3. **Contrôle Strict des Risques (Partie X)** : Plafonds d'exposition **$\le 15\%$** par ligne et **$\le 50\%$** par secteur.
    4. **Mémoire Longitudinal (Partie V)** : Suivi hebdomadaire des scores ($S_1, S_2, \dots$) pour anticiper l'essoufflement des fondamentaux.
    5. **Signaux Contrarians (Partie VII)** : Détection automatique et suivi des anomalies de marché (Sur-réactions, Catalyseurs négligés, Dératings, Momentum).
    """)

if df_screening.empty:
    st.warning(
        "Aucune donnée dans la base. Exécutez `boc_scraper.py` pour alimenter le screener."
    )
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Screener & Graphiques",
        "🧮 Simulateur (Nets SGI)",
        "💼 Mon Portefeuille",
        "🔬 Analyse Fondamentale & Value",
        "⚡ Signaux Contrarians (Partie VII)",
    ])

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
                title=f"Évolution du cours - {ticker_choisi}",
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
                df_merged[cols_show].style.format({
                    "prix_achat": "{:,.0f} FCFA",
                    "Cours Actuel": "{:,.0f} FCFA",
                    "Investissement Total": "{:,.0f} FCFA",
                    "Valeur Nette Estimation": "{:,.0f} FCFA",
                    "Gain Net FCFA": "{:,.0f} FCFA",
                    "Performance Net (%)": "{:+.2f}%",
                }),
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

            # --- TRAÇABILITÉ DES GRADES ET SUIVI LONGITUDINAL ---
            st.markdown("---")
            st.subheader(
                "📜 Traçabilité des Grades (Gate) & Suivi Longitudinal (Parties III, IV, V)"
            )

            df_long = charger_suivi_longitudinal()

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

            if not df_long.empty:
                st.markdown("#### 📊 Évolution Multisemaines des Scores par Titre")

                df_pivot = df_long.pivot(
                    index="ticker",
                    columns="semaine",
                    values="score_fondamental",
                )

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

    # --- ONGLET 5 : SIGNAUX CONTRARIANS (PARTIE VII) ---
    with tab5:
        st.subheader(
            "⚡ Module Signaux Contrarians — Détection & Suivi (Partie VII)"
        )

        st.markdown("""
        Ce module analyse l'ensemble des entreprises de la BRVM pour identifier les anomalies de marché selon les 4 archétypes de la **Partie VII (MBC-METH-2026-07-001)** :
        * **Archétype 1 : Sur-réaction négative** (Chute illégitime avec dividende/fondamentaux intacts).
        * **Archétype 2 : Catalyseur négligé** (Événement/dividende proche ignoré par le cours).
        * **Archétype 3 : Dérating prolongé** (PER très bas avec cours stabilisé mais carnet à valider).
        * **Archétype 4 : Momentum sous-estimé** (Accélération du volume et résorption du mur vendeur).
        """)

        st.markdown("---")
        st.markdown(
            "### 🤖 1. Détection Automatique en Temps Réel (Scanner BRVM)"
        )

        df_auto_signaux = detecter_signaux_contrarians_auto(
            df_screening, financials_dict
        )

        if df_auto_signaux.empty:
            st.info(
                "Conformément à la règle de la Partie VII.3 : Aucun signal contrarian net n'a été détecté automatiquement cette semaine. La section reste volontairement sélective."
            )
        else:
            st.dataframe(df_auto_signaux, use_container_width=True)

            with st.expander(
                "➕ Enregistrer un signal détecté dans le registre de suivi"
            ):
                col_c1, col_c2, col_c3 = st.columns(3)
                with col_c1:
                    sig_ticker = st.selectbox(
                        "Action :",
                        df_auto_signaux["Ticker"].unique(),
                        key="sig_t_auto",
                    )
                    sig_sem = st.text_input(
                        "Identifiant Semaine / BOC :",
                        value="BOC N°167 (04/09)",
                        key="sig_s_auto",
                    )
                with col_c2:
                    sig_arch = st.selectbox(
                        "Archétype :",
                        [
                            "Archétype 1 — Sur-réaction négative",
                            "Archétype 2 — Catalyseur négligé",
                            "Archétype 3 — Dérating prolongé",
                            "Archétype 4 — Momentum sous-estimé",
                        ],
                        key="sig_a_auto",
                    )
                    sig_conv = st.selectbox(
                        "Conviction :",
                        ["FORTE", "MOYENNE-FORTE", "MOYENNE", "FAIBLE"],
                        key="sig_c_auto",
                    )
                with col_c3:
                    sig_elem = st.text_input(
                        "Élément ignoré par le marché :",
                        value="Anomalie de prix détectée",
                        key="sig_e_auto",
                    )
                    sig_risq = st.text_input(
                        "Risque principal :",
                        value="Pression résiduelle carnet",
                        key="sig_r_auto",
                    )

                if st.button("💾 Ajouter au registre SQLite `signaux_contrarians`"):
                    enregistrer_signal_contrarian(
                        ticker=sig_ticker,
                        semaine=sig_sem,
                        archetype=sig_arch,
                        conviction=sig_conv,
                        element_ignore=sig_elem,
                        risque_principal=sig_risq,
                    )
                    st.success(
                        f"Signal sur {sig_ticker} ajouté avec succès au registre !"
                    )
                    st.rerun()

        st.markdown("---")
        st.markdown(
            "### 📜 2. Registre d'Historique et Suivi des Verdicts (BOC N°162 à N°167+)"
        )

        df_signaux_db = charger_signaux_contrarians()

        if df_signaux_db.empty:
            st.info("Aucun signal enregistré dans la base de données.")
        else:
            st.dataframe(
                df_signaux_db[[
                    "id",
                    "ticker",
                    "semaine",
                    "archetype",
                    "conviction",
                    "element_ignore",
                    "risque_principal",
                    "evolution",
                    "verdict",
                ]],
                use_container_width=True,
            )

            st.markdown("#### 🔄 Mettre à jour l'évolution et le verdict d'un signal")
            with st.expander("✏️ Éditer le statut d'un signal"):
                sig_edit_id = st.selectbox(
                    "Sélectionner l'ID du signal :",
                    df_signaux_db["id"].tolist(),
                    key="sig_edit_id_sel",
                )
                row_sel = df_signaux_db[
                    df_signaux_db["id"] == sig_edit_id
                ].iloc[0]

                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    u_ticker = st.text_input(
                        "Ticker", value=row_sel["ticker"], disabled=True
                    )
                    u_semaine = st.text_input(
                        "Semaine", value=row_sel["semaine"], disabled=True
                    )
                with col_e2:
                    u_evolution = st.text_area(
                        "Évolution constatée :",
                        value=row_sel["evolution"] or "",
                    )
                with col_e3:
                    u_verdict = st.selectbox(
                        "Verdict :",
                        ["EN COURS", "VALIDÉ", "NEUTRE", "RISQUE CONFIRMÉ"],
                        index=[
                            "EN COURS",
                            "VALIDÉ",
                            "NEUTRE",
                            "RISQUE CONFIRMÉ",
                        ].index(row_sel["verdict"]),
                    )

                if st.button("💾 Mettre à jour le verdict"):
                    enregistrer_signal_contrarian(
                        ticker=row_sel["ticker"],
                        semaine=row_sel["semaine"],
                        archetype=row_sel["archetype"],
                        conviction=row_sel["conviction"],
                        element_ignore=row_sel["element_ignore"],
                        risque_principal=row_sel["risque_principal"],
                        evolution=u_evolution,
                        verdict=u_verdict,
                        date_signal=row_sel["date_signal"],
                    )
                    st.success("Verdict mis à jour !")
                    st.rerun()

            with st.expander("🗑️ Supprimer un signal du registre"):
                sig_del_id = st.selectbox(
                    "Sélectionner l'ID du signal à supprimer :",
                    df_signaux_db["id"].tolist(),
                    key="sig_del_id_sel",
                )
                if st.button("Confirmer la suppression du signal"):
                    supprimer_signal_contrarian(sig_del_id)
                    st.success("Signal supprimé.")
                    st.rerun()