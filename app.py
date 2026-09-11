import datetime
import os
import sqlite3
import google.generativeai as genai
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


# --- LEXIQUE LOCAL & INTÉGRATION IA GEMINI ---
LEXIQUE_FINANCIER = {
    "BPA": "Bénéfice Par Action : Résultat net divisé par le nombre total d'actions.",
    "VNC": "Valeur Nette Comptable par action : Capitaux propres divisés par le nombre d'actions.",
    "PER": "Price Earnings Ratio : Cours de l'action divisé par le BPA (mesure la cherté d'un titre).",
    "GRAHAM": "Nombre de Graham : Formule évaluant le prix plafond théorique d'une action Value.",
    "SGI": "Société de Gestion et d'Intermédiation : Courtier agréé sur la bourse de la BRVM.",
    "BOC": "Bulletin Officiel de la Cote : Journal officiel récapitulant les transactions boursières.",
    "YIELD": "Rendement du dividende : Montant du dividende divisé par le cours de bourse.",
    "FLOTTANT": "Pourcentage d'actions réellement en circulation et négociables en bourse.",
}


def get_gemini_model():
    """Initialise l'API Gemini via les secrets Streamlit ou la variable d'environnement."""
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    return None


@st.cache_data(show_spinner=False)
def traduire_ou_expliquer_terme(terme: str) -> str:
    """Consulte en priorité le dictionnaire local, puis Gemini si le terme est inconnu."""
    if not terme or not str(terme).strip():
        return ""

    terme_clean = str(terme).strip()
    terme_upper = terme_clean.upper()

    # 1. Vérification dans le lexique local
    if terme_upper in LEXIQUE_FINANCIER:
        return LEXIQUE_FINANCIER[terme_upper]

    # 2. Interrogation de l'IA Gemini
    model = get_gemini_model()
    if not model:
        return f"💡 **{terme_clean}** : Définition locale indisponible."

    try:
        prompt = f"Explique le terme boursier ou financier '{terme_clean}' en une sentence simple et très concise en français."
        response = model.generate_content(prompt)
        return f"🤖 **{terme_clean}** : {response.text.strip()}"
    except Exception:
        return f"💡 **{terme_clean}** : Définition temporairement indisponible."


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

    # 2. Table Suivi Longitudinal
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

    # 3. Table Signaux Contrarians
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
            prix_entree REAL DEFAULT 0,
            prix_cible REAL DEFAULT 0,
            stop_loss REAL DEFAULT 0,
            prix_cloture REAL DEFAULT 0,
            UNIQUE(ticker, semaine, archetype) ON CONFLICT REPLACE
        )
    """)

    # Migrations sécurisées des colonnes optionnelles
    for col, col_type in [
        ("date_grade", "TEXT"),
        ("prix_entree", "REAL DEFAULT 0"),
        ("prix_cible", "REAL DEFAULT 0"),
        ("stop_loss", "REAL DEFAULT 0"),
        ("prix_cloture", "REAL DEFAULT 0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE signaux_contrarians ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    conn.commit()

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
                7000.0,
                7800.0,
                6600.0,
                7350.0
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
                "INVALIDÉ",
                2350.0,
                2600.0,
                2200.0,
                2180.0
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO signaux_contrarians 
            (ticker, semaine, date_signal, archetype, conviction, element_ignore, risque_principal, evolution, verdict, prix_entree, prix_cible, stop_loss, prix_cloture)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            exemples_signaux,
        )
        conn.commit()

    conn.close()


# --- FONCTIONS UTILITAIRES ---
def verifier_peremption_grade(grade, date_grade_str):
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
        {"Ticker": "NTLC", "Nom": "NESTLE CI", "Cours (FCFA)": 7200, "Variation (%)": 2.21, "Volume": 3450},
        {"Ticker": "ABJC", "Nom": "SERVAIR ABIDJAN", "Cours (FCFA)": 3880, "Variation (%)": -1.27, "Volume": 1200},
        {"Ticker": "SMBC", "Nom": "SMB CI", "Cours (FCFA)": 17400, "Variation (%)": 1.16, "Volume": 5800},
        {"Ticker": "BOAC", "Nom": "BANK OF AFRICA CI", "Cours (FCFA)": 6900, "Variation (%)": 0.00, "Volume": 890},
        {"Ticker": "NEIC", "Nom": "NEI-CEDA CI", "Cours (FCFA)": 650, "Variation (%)": 0.00, "Volume": 4192},
        {"Ticker": "TTLC", "Nom": "TOTALENERGIES CI", "Cours (FCFA)": 2350, "Variation (%)": 0.60, "Volume": 2100},
        {"Ticker": "SGBC", "Nom": "SOCIETE GENERALE CI", "Cours (FCFA)": 18200, "Variation (%)": -0.82, "Volume": 4100},
        {"Ticker": "SNTS", "Nom": "SONATEL SENEGAL", "Cours (FCFA)": 19500, "Variation (%)": 1.56, "Volume": 12500},
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

    dates = pd.date_range(end=datetime.date.today(), periods=10).strftime("%Y-%m-%d")
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
        "INSERT INTO portefeuille (ticker, quantite, prix_achat, date_achat) VALUES (?, ?, ?, ?)",
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


def enregistrer_suivi_semaine(ticker, semaine, score, grade="NE", date_grade=None, ratio_liq=None, commentaire="", date_eng=None):
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
        (ticker, semaine, date_eng, score, grade, date_grade, ratio_liq, commentaire),
    )
    conn.commit()
    conn.close()


def charger_suivi_longitudinal():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM suivi_longitudinal ORDER BY ticker, semaine ASC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def charger_signaux_contrarians():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query("SELECT * FROM signaux_contrarians ORDER BY date_signal DESC, ticker ASC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def enregistrer_signal_contrarian(ticker, semaine, archetype, conviction, element_ignore, risque_principal, evolution="", verdict="EN COURS", date_signal=None, prix_entree=0, prix_cible=0, stop_loss=0, prix_cloture=0):
    if date_signal is None:
        date_signal = datetime.date.today().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO signaux_contrarians 
        (ticker, semaine, date_signal, archetype, conviction, element_ignore, risque_principal, evolution, verdict, prix_entree, prix_cible, stop_loss, prix_cloture)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, semaine, archetype) DO UPDATE SET
            date_signal = excluded.date_signal,
            conviction = excluded.conviction,
            element_ignore = excluded.element_ignore,
            risque_principal = excluded.risque_principal,
            evolution = excluded.evolution,
            verdict = excluded.verdict,
            prix_entree = excluded.prix_entree,
            prix_cible = excluded.prix_cible,
            stop_loss = excluded.stop_loss,
            prix_cloture = excluded.prix_cloture
    """,
        (ticker, semaine, date_signal, archetype, conviction, element_ignore, risque_principal, evolution, verdict, prix_entree, prix_cible, stop_loss, prix_cloture),
    )
    conn.commit()
    conn.close()


def supprimer_signal_contrarian(signal_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM signaux_contrarians WHERE id = ?", (signal_id,))
    conn.commit()
    conn.close()


def detecter_signaux_contrarians_auto(df_screening, financials_dict):
    signaux = []
    for _, row in df_screening.iterrows():
        ticker = row.get("Ticker")
        cours = float(row.get("Cours (FCFA)", 0))
        var = float(row.get("Variation (%)", 0))

        fin = financials_dict.get(ticker, {})
        div = float(fin.get("Dividende", 0))
        rendement_div = (div / cours * 100) if cours > 0 else 0

        if var <= -1.0 and rendement_div >= 4.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 1 — Sur-réaction négative",
                "Élément ignoré par le marché": f"Repli de {var:.2f} % alors que le rendement du dividende ({rendement_div:.1f} %) est intact.",
                "Risque principal": "Pression vendeuse résiduelle à court terme.",
                "Conviction": "MOYENNE",
            })
        elif rendement_div >= 4.0 and -1.0 < var < 1.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 2 — Catalyseur négligé",
                "Élément ignoré par le marché": f"Dividende de {div:,.0f} FCFA ({rendement_div:.1f} %) à peine intégré par le cours ({var:+.2f} %).",
                "Risque principal": "Passivité du marché jusqu'au détachement.",
                "Conviction": "MOYENNE-FORTE",
            })
    return pd.DataFrame(signaux)


def creer_jauge_concentration(titre, valeur, seuil, max_val=100):
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
                "axis": {"range": [0, max_val], "tickwidth": 1, "tickcolor": "gray"},
                "bar": {"color": couleur_barre},
                "bgcolor": "white",
                "borderwidth": 1,
                "bordercolor": "gray",
                "steps": [
                    {"range": [0, seuil], "color": "rgba(0, 204, 150, 0.15)"},
                    {"range": [seuil, max_val], "color": "rgba(255, 43, 43, 0.2)"},
                ],
                "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": seuil},
            },
        )
    )
    fig.update_layout(height=210, margin=dict(l=20, r=20, t=50, b=10), font={"family": "Arial"})
    return fig


# --- DÉMARRAGE BASE DE DONNÉES ET DONNÉES ---
init_tables_sqlite()
df_screening = charger_donnees_screening()
financials_dict = fundamentals.charger_financials()


# --- BARRE LATÉRALE ---
st.sidebar.title("🎛️ Panneau de Contrôle")
st.sidebar.header("🔍 Filtres du Screener")

recherche_ticker = st.sidebar.text_input("Rechercher un Ticker :", "").strip().upper()

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
    st.sidebar.number_input("Volume minimum :", min_value=0, value=0, step=100)
    if not df_screening.empty and "Volume" in df_screening.columns
    else 0
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuration SGI")
taux_frais_sgi = (
    st.sidebar.slider("Taux de frais SGI (%)", min_value=0.5, max_value=3.0, value=1.5, step=0.1)
    / 100
)

# --- MODULE ASSISTANT / DICTIONNAIRE DANS LA SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.header("📖 Dictionnaire & Assistant IA")
mot_a_traduire = st.sidebar.text_input("Rechercher la définition d'un terme :", placeholder="ex: PER, BPA, Graham...")
if mot_a_traduire:
    definition_trouvee = traduire_ou_expliquer_terme(mot_a_traduire)
    st.sidebar.info(definition_trouvee)

# Filtres appliqués
df_filtre = df_screening.copy()
if not df_filtre.empty:
    if recherche_ticker:
        df_filtre = df_filtre[df_filtre["Ticker"].str.contains(recherche_ticker, case=False, na=False)]
    if "Variation (%)" in df_filtre.columns:
        df_filtre = df_filtre[(df_filtre["Variation (%)"] >= var_range[0]) & (df_filtre["Variation (%)"] <= var_range[1])]
    if "Volume" in df_filtre.columns:
        df_filtre = df_filtre[df_filtre["Volume"] >= min_volume]


# --- EN-TÊTE ET ONGLETS PRINCIPAUX ---
st.title("📊 BRVM Quantum Analytics")

with st.expander("ℹ️ Résumé de la Méthodologie & Cadre de Décision (MBC-METH-2026-07-001)"):
    st.markdown("""
    **BRVM Quantum Analytics** applique une discipline stricte en 5 piliers non négociables :
    1. **Valuation Value & Graham (Partie IV)** : Sélection des titres présentant un score fondamental élevé et une marge de sécurité via le Nombre de Graham.
    2. **Traçabilité des Grades / Gate (Partie III)** : Attribution d'un Grade de Zone ($A, B, C, NE$) horodaté avec **règle de péremption stricte à 21 jours**.
    3. **Contrôle Strict des Risques & R:R (Partie X)** : Plafonds d'exposition ($\le 15\%$ par ligne / $\le 50\%$ par secteur) et validation du Ratio Gain/Risque.
    4. **Mémoire Longitudinal (Partie V)** : Suivi hebdomadaire des scores ($S_1, S_2, \dots$) pour anticiper l'essoufflement des fondamentaux.
    5. **Signaux Contrarians & Track-Record (Partie VII)** : Détection automatique, suivi et mesure du Win-Rate réel des opportunités contrarians.
    """)

if df_screening.empty:
    st.warning("Aucune donnée dans la base. Exécutez le scraper pour alimenter le screener.")
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Screener & Graphiques",
        "🧮 Simulateur & Risk R:R",
        "💼 Mon Portefeuille",
        "🔬 Analyse Fondamentale & Value",
        "⚡ Signaux Contrarians & Track-Record",
    ])

    # --- ONGLET 1 : SCREENER ---
    with tab1:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Actions Sélectionnées", f"{len(df_filtre)} / {len(df_screening)}")
        k2.metric("Hausses 🚀", len(df_filtre[df_filtre["Variation (%)"] > 0]) if "Variation (%)" in df_filtre.columns else 0)
        k3.metric("Baisses 🔻", len(df_filtre[df_filtre["Variation (%)"] < 0]) if "Variation (%)" in df_filtre.columns else 0)
        k4.metric("Volume Filtré", f"{df_filtre['Volume'].sum():,.0f}" if "Volume" in df_filtre.columns else "0")

        st.markdown("---")
        st.dataframe(df_filtre, use_container_width=True)

        st.markdown("---")
        ticker_choisi = st.selectbox("Historique du cours :", df_screening["Ticker"].unique(), key="s1_t")
        df_hist = charger_historique_ticker(ticker_choisi)
        if not df_hist.empty:
            fig = px.line(df_hist, x="date", y="cours", title=f"Évolution du cours - {ticker_choisi}", markers=True)
            st.plotly_chart(fig, use_container_width=True)

    # --- ONGLET 2 : SIMULATEUR & RISK R:R ---
    with tab2:
        st.subheader("1. Simulateur de Rendement Net SGI")
        c1, c2, c3 = st.columns(3)
        with c1:
            action_simu = st.selectbox("Action :", df_screening["Ticker"].unique(), key="sim_t")
            cours_actuel = df_screening.loc[df_screening["Ticker"] == action_simu, "Cours (FCFA)"].values[0]
        with c2:
            prix_achat = st.number_input("Prix Achat Unitaire (FCFA)", value=float(cours_actuel), step=50.0)
            quantite = st.number_input("Quantité", value=100, min_value=1)
        with c3:
            prix_vente = st.number_input("Prix Vente Estimé (FCFA)", value=float(round(cours_actuel * 1.1)), step=50.0)

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

        st.markdown("---")
        st.subheader("2. Calculateur de Ratio Rendement / Risque (R:R) avec Stop-Loss")
        
        rr_col1, rr_col2, rr_col3 = st.columns(3)
        with rr_col1:
            rr_entree = st.number_input("Prix d'Entrée (FCFA)", value=float(cours_actuel), step=25.0, key="rr_e")
        with rr_col2:
            rr_cible = st.number_input("Prix Cible / Objectif (FCFA)", value=float(round(cours_actuel * 1.2)), step=25.0, key="rr_c")
        with rr_col3:
            rr_stop = st.number_input("Stop-Loss / Invalidation (FCFA)", value=float(round(cours_actuel * 0.9)), step=25.0, key="rr_s")

        if rr_stop >= rr_entree:
            st.error("⚠️ Le Stop-Loss doit être STRICTEMENT inférieur au Prix d'Entrée.")
        elif rr_cible <= rr_entree:
            st.warning("⚠️ Le Prix Cible doit être supérieur au Prix d’Entrée.")
        else:
            gain_brut_unit = rr_cible - rr_entree
            risque_brut_unit = rr_entree - rr_stop
            rr_brut = gain_brut_unit / risque_brut_unit

            # Prise en compte des frais SGI
            achat_net = rr_entree * (1 + taux_frais_sgi)
            vente_cible_nette = rr_cible * (1 - taux_frais_sgi)
            vente_stop_nette = rr_stop * (1 - taux_frais_sgi)

            gain_net_unit = vente_cible_nette - achat_net
            risque_net_unit = achat_net - vente_stop_nette
            rr_net = gain_net_unit / risque_net_unit if risque_net_unit > 0 else 0

            r_m1, r_m2, r_m3, r_m4 = st.columns(4)
            r_m1.metric("Gain Net Potentiel", f"{gain_net_unit:,.0f} FCFA", f"+{(gain_net_unit/achat_net)*100:.2f}%")
            r_m2.metric("Risque Net Maximale", f"{risque_net_unit:,.0f} FCFA", f"-{(risque_net_unit/achat_net)*100:.2f}%", delta_color="inverse")
            r_m3.metric("Ratio R:R Brut", f"1 : {rr_brut:.2f}")

            badge_rr = "🟢 Excellent (≥ 1:2.5)" if rr_net >= 2.5 else ("🟡 Valide (≥ 1:1.5)" if rr_net >= 1.5 else "🔴 Insuffisant (< 1:1.5)")
            r_m4.metric("Ratio R:R Net SGI", f"1 : {rr_net:.2f}", badge_rr)

            if rr_net < 1.5:
                st.error("❌ **Position Risquée** : Le ratio Gain/Risque net est trop faible (< 1:1.5). Revoir l'objectif ou serrer le Stop-Loss.")
            else:
                st.success(f"✅ **Position Validée** : Pour 1 FCFA risqué, vous visez {rr_net:.2f} FCFA de gain net.")

    # --- ONGLET 3 : PORTEFEUILLE ---
    with tab3:
        st.subheader("📌 Ajouter une Ligne d'Achat")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            p_ticker = st.selectbox("Action :", df_screening["Ticker"].unique(), key="p_tick")
            cours_ref = df_screening.loc[df_screening["Ticker"] == p_ticker, "Cours (FCFA)"].values[0]
        with col_p2:
            p_qte = st.number_input("Quantité :", min_value=1, value=50, key="p_q")
        with col_p3:
            p_prix = st.number_input("Prix d'Achat Unitaire (FCFA) :", value=float(cours_ref), step=50.0, key="p_pr")
        with col_p4:
            p_date = st.date_input("Date d'achat :", datetime.date.today(), key="p_d")

        if st.button("➕ Ajouter au portefeuille"):
            ajouter_position(p_ticker, p_qte, p_prix, str(p_date))
            st.success(f"Position sur {p_ticker} ajoutée !")
            st.rerun()

        st.markdown("---")
        df_port = charger_portefeuille()

        if df_port.empty:
            st.info("Votre portefeuille est actuellement vide.")
        else:
            df_merged = df_port.merge(df_screening[["Ticker", "Cours (FCFA)"]], left_on="ticker", right_on="Ticker", how="left")
            df_merged["Cours Actuel"] = df_merged["Cours (FCFA)"].fillna(df_merged["prix_achat"])
            df_merged["Cout Achat Brut"] = df_merged["quantite"] * df_merged["prix_achat"]
            df_merged["Frais Achat"] = df_merged["Cout Achat Brut"] * taux_frais_sgi
            df_merged["Investissement Total"] = df_merged["Cout Achat Brut"] + df_merged["Frais Achat"]
            df_merged["Valeur Actuelle Brute"] = df_merged["quantite"] * df_merged["Cours Actuel"]
            df_merged["Frais Vente Est."] = df_merged["Valeur Actuelle Brute"] * taux_frais_sgi
            df_merged["Valeur Nette Estimation"] = df_merged["Valeur Actuelle Brute"] - df_merged["Frais Vente Est."]
            df_merged["Gain Net FCFA"] = df_merged["Valeur Nette Estimation"] - df_merged["Investissement Total"]
            df_merged["Performance Net (%)"] = (df_merged["Gain Net FCFA"] / df_merged["Investissement Total"]) * 100
            df_merged["Secteur"] = df_merged["ticker"].apply(lambda t: financials_dict.get(t, {}).get("Secteur", "Inconnu"))

            tot_investi = df_merged["Investissement Total"].sum()
            tot_valeur_nette = df_merged["Valeur Nette Estimation"].sum()
            tot_gain_net = tot_valeur_nette - tot_investi
            tot_perf_pct = (tot_gain_net / tot_investi) * 100 if tot_investi > 0 else 0

            kp1, kp2, kp3, kp4 = st.columns(4)
            kp1.metric("Capital Investi", f"{tot_investi:,.0f} FCFA")
            kp2.metric("Valeur Nette Total", f"{tot_valeur_nette:,.0f} FCFA")
            kp3.metric("Gain Net FCFA", f"{tot_gain_net:,.0f} FCFA", delta=f"{tot_perf_pct:.2f}%")
            kp4.metric("Lignes Ouvertes", len(df_merged))

            st.markdown("---")
            st.markdown("### 🛡️ Contrôle & Jauges de Risque (Partie X)")

            df_poids_ligne = df_merged.groupby("ticker")["Valeur Nette Estimation"].sum().reset_index()
            df_poids_ligne["Poids (%)"] = (df_poids_ligne["Valeur Nette Estimation"] / tot_valeur_nette) * 100
            df_poids_secteur = df_merged.groupby("Secteur")["Valeur Nette Estimation"].sum().reset_index()
            df_poids_secteur["Poids (%)"] = (df_poids_secteur["Valeur Nette Estimation"] / tot_valeur_nette) * 100

            max_ligne = df_poids_ligne.sort_values("Poids (%)", ascending=False).iloc[0]
            max_secteur = df_poids_secteur.sort_values("Poids (%)", ascending=False).iloc[0]

            jauge_col1, jauge_col2 = st.columns(2)
            with jauge_col1:
                fig_jauge_ligne = creer_jauge_concentration(f"Ligne max ({max_ligne['ticker']})", max_ligne["Poids (%)"], seuil=15.0)
                st.plotly_chart(fig_jauge_ligne, use_container_width=True)
            with jauge_col2:
                fig_jauge_secteur = creer_jauge_concentration(f"Secteur max ({max_secteur['Secteur']})", max_secteur["Poids (%)"], seuil=50.0)
                st.plotly_chart(fig_jauge_secteur, use_container_width=True)

            cols_show = ["id", "ticker", "Secteur", "quantite", "prix_achat", "Cours Actuel", "Investissement Total", "Valeur Nette Estimation", "Gain Net FCFA", "Performance Net (%)"]
            st.dataframe(df_merged[cols_show], use_container_width=True)

            with st.expander("🗑️ Supprimer une ligne de position"):
                del_id = st.selectbox("Sélectionner l'ID à supprimer :", df_merged["id"].tolist())
                if st.button("Confirmer la suppression"):
                    supprimer_position(del_id)
                    st.rerun()

    # --- ONGLET 4 : ANALYSE FONDAMENTALE & GRAHAM ---
    with tab4:
        st.subheader("🔬 Analyse Fondamentale & Valuation (Graham / Value)")
        ticker_fund = st.selectbox("Sélectionner une action à analyser :", df_screening["Ticker"].unique(), key="fund_select")

        cours_f = (
            df_screening.loc[df_screening["Ticker"] == ticker_fund, "Cours (FCFA)"].values[0]
            if not df_screening.empty
            else 0
        )

        fin = financials_dict.get(ticker_fund, {})
        bpa = float(fin.get("BPA", 0))
        vnc = float(fin.get("VNC", 0))
        per = float(fin.get("PER", 0))
        nom_entreprise = fin.get("Nom", ticker_fund)
        secteur_entreprise = fin.get("Secteur", "Inconnu")

        nombre_graham = (22.5 * bpa * vnc) ** 0.5 if bpa > 0 and vnc > 0 else 0
        marge_securite = ((nombre_graham - cours_f) / nombre_graham * 100) if nombre_graham > 0 else 0

        st.markdown(f"### 📋 Métriques de Valuation — {nom_entreprise} ({ticker_fund})")
        st.caption(f"Secteur : {secteur_entreprise}")

        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Cours Actuel", f"{cours_f:,.0f} FCFA")
        f2.metric("Nombre de Graham", f"{nombre_graham:,.0f} FCFA" if nombre_graham > 0 else "N/A", help=traduire_ou_expliquer_terme("GRAHAM"))
        f3.metric("Marge de Sécurité", f"{marge_securite:+.1f}%" if nombre_graham > 0 else "N/A")
        f4.metric("PER", f"{per:.1f}x" if per > 0 else "N/A", help=traduire_ou_expliquer_terme("PER"))

        st.markdown("---")
        st.markdown("### 📝 Enregistrement du Suivi Longitudinal (Parties III, IV & V)")

        with st.form(key=f"form_suivi_{ticker_fund}"):
            c_s1, c_s2, c_s3 = st.columns(3)
            with c_s1:
                semaine_input = st.text_input("Semaine (ex: 2026-W37)", value=datetime.date.today().strftime("%Y-W%W"))
                score_input = st.number_input("Score Fondamental (0 à 10)", min_value=0.0, max_value=10.0, value=7.0, step=0.5)
            with c_s2:
                grade_input = st.selectbox("Grade de Zone", ["NE", "A", "B", "C"], help=traduire_ou_expliquer_terme("GRADE"))
                date_grade_input = st.date_input("Date d'attribution du Grade", datetime.date.today())
            with c_s3:
                ratio_liq_input = st.number_input("Ratio de Liquidité", min_value=0.0, value=1.0, step=0.1)
                commentaire_input = st.text_area("Commentaire / Observation", value="", height=68)

            btn_save_suivi = st.form_submit_button("💾 Enregistrer le Suivi Weekly")

        if btn_save_suivi:
            enregistrer_suivi_semaine(
                ticker=ticker_fund,
                semaine=semaine_input,
                score=score_input,
                grade=grade_input,
                date_grade=str(date_grade_input),
                ratio_liq=ratio_liq_input,
                commentaire=commentaire_input,
            )
            st.success(f"Suivi pour {ticker_fund} ({semaine_input}) enregistré !")
            st.rerun()

        st.markdown("---")
        st.markdown("### 📜 Historique Longitudinal & Statut des Grades")
        df_suivi = charger_suivi_longitudinal()
        if not df_suivi.empty:
            df_suivi_ticker = df_suivi[df_suivi["ticker"] == ticker_fund]
            if not df_suivi_ticker.empty:
                derniere_ligne = df_suivi_ticker.iloc[-1]
                statut_grade, couleur_grade, perime = verifier_peremption_grade(
                    derniere_ligne.get("grade_zone"),
                    derniere_ligne.get("date_grade"),
                )
                if perime:
                    st.warning(f"Statut du Grade : {statut_grade}")
                else:
                    st.success(f"Statut du Grade : {statut_grade}")

                st.dataframe(df_suivi_ticker, use_container_width=True)

                fig_score = px.line(
                    df_suivi_ticker,
                    x="semaine",
                    y="score_fondamental",
                    title=f"Évolution du Score Fondamental — {ticker_fund}",
                    markers=True,
                )
                st.plotly_chart(fig_score, use_container_width=True)

    # --- ONGLET 5 : SIGNAUX CONTRARIANS & TRACK-RECORD ---
    with tab5:
        st.subheader("⚡ Détection & Track-Record des Signaux Contrarians (Partie VII)")

        # TRACK-RECORD SUMMARY
        df_signaux = charger_signaux_contrarians()
        
        st.markdown("#### 🏆 Track-Record & Performance Global")
        if not df_signaux.empty:
            df_clotures = df_signaux[df_signaux["verdict"].isin(["VALIDÉ", "INVALIDÉ", "RISQUE CONFIRMÉ"])].copy()
            total_clotures = len(df_clotures)
            
            if total_clotures > 0:
                valides = len(df_clotures[df_clotures["verdict"] == "VALIDÉ"])
                win_rate = (valides / total_clotures) * 100
                
                # Calcul perf si prix enregistrés
                df_clotures["perf_pct"] = df_clotures.apply(
                    lambda r: ((r["prix_cloture"] - r["prix_entree"]) / r["prix_entree"] * 100) if r["prix_entree"] > 0 and r["prix_cloture"] > 0 else (5.0 if r["verdict"] == "VALIDÉ" else -3.0),
                    axis=1
                )
                perf_moyenne = df_clotures["perf_pct"].mean()

                tk1, tk2, tk3, tk4 = st.columns(4)
                tk1.metric("Signaux Clôturés", total_clotures)
                tk2.metric("Taux de Réussite (Win-Rate)", f"{win_rate:.1f}%", f"{valides} GAGNANTS")
                tk3.metric("Performance Moyenne Net", f"{perf_moyenne:+.2f}%")
                tk4.metric("Signaux En Cours", len(df_signaux[df_signaux["verdict"] == "EN COURS"]))
            else:
                st.info("Aucun signal clôturé pour le moment. Le Win-Rate s'affichera dès qu'un signal passera au statut VALIDÉ ou INVALIDÉ.")
        
        st.markdown("---")
        st.markdown("#### 🤖 Signaux Détectés Automatiquement")
        df_auto = detecter_signaux_contrarians_auto(df_screening, financials_dict)

        if not df_auto.empty:
            st.dataframe(df_auto, use_container_width=True)
        else:
            st.info("Aucun signal contrarian automatique détecté selon les critères actuels.")

        st.markdown("---")
        st.markdown("#### ➕ Enregistrer ou Mettre à jour un Signal")

        with st.form("form_signal_contrarian"):
            c1_sig, c2_sig, c3_sig = st.columns(3)
            with c1_sig:
                sig_ticker = st.selectbox("Ticker", df_screening["Ticker"].unique(), key="sig_t")
                sig_semaine = st.text_input("Semaine (ex: BOC N°168)", value="BOC N°168", help=traduire_ou_expliquer_terme("BOC"))
                sig_archetype = st.selectbox(
                    "Archétype",
                    [
                        "Archétype 1 — Sur-réaction négative",
                        "Archétype 2 — Catalyseur négligé",
                        "Archétype 3 — Dérating prolongé",
                        "Archétype 4 — Momentum sous-estimé",
                    ],
                )
                sig_conviction = st.selectbox("Niveau de Conviction", ["FAIBLE", "MOYENNE", "MOYENNE-FORTE", "FORTE"])
            
            with c2_sig:
                sig_verdict = st.selectbox("Verdict / Statut", ["EN COURS", "VALIDÉ", "NEUTRE", "RISQUE CONFIRMÉ", "INVALIDÉ"])
                sig_date = st.date_input("Date du Signal", datetime.date.today())
                sig_prix_entree = st.number_input("Prix Entrée (FCFA)", min_value=0.0, value=0.0, step=50.0)
                sig_prix_cible = st.number_input("Prix Cible (FCFA)", min_value=0.0, value=0.0, step=50.0)

            with c3_sig:
                sig_stop_loss = st.number_input("Stop-Loss (FCFA)", min_value=0.0, value=0.0, step=50.0)
                sig_prix_cloture = st.number_input("Prix de Clôture (FCFA)", min_value=0.0, value=0.0, step=50.0)
                sig_ignore = st.text_area("Élément ignoré par le marché", value="", height=68)

            sig_risque = st.text_area("Risque Principal", value="", height=50)
            sig_evolution = st.text_area("Évolution / Observations", value="", height=50)
            
            btn_sig = st.form_submit_button("💾 Enregistrer le Signal dans le Track-Record")

        if btn_sig:
            enregistrer_signal_contrarian(
                ticker=sig_ticker,
                semaine=sig_semaine,
                archetype=sig_archetype,
                conviction=sig_conviction,
                element_ignore=sig_ignore,
                risque_principal=sig_risque,
                evolution=sig_evolution,
                verdict=sig_verdict,
                date_signal=str(sig_date),
                prix_entree=sig_prix_entree,
                prix_cible=sig_prix_cible,
                stop_loss=sig_stop_loss,
                prix_cloture=sig_prix_cloture,
            )
            st.success(f"Signal pour {sig_ticker} enregistré dans le Track-Record !")
            st.rerun()

        st.markdown("---")
        st.markdown("#### 📜 Historique complet du Track-Record")
        if not df_signaux.empty:
            st.dataframe(df_signaux, use_container_width=True)
            
            with st.expander("🗑️ Supprimer un signal de l'historique"):
                del_sig_id = st.selectbox("Sélectionner l'ID du signal à supprimer :", df_signaux["id"].tolist())
                if st.button("Confirmer la suppression du signal"):
                    supprimer_signal_contrarian(del_sig_id)
                    st.success("Signal supprimé !")
                    st.rerun()