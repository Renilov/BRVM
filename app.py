import datetime
import os
import sqlite3
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import fundamentals

try:
    from actualiser_donnees import synchroniser_brvm_web
except ImportError:
    synchroniser_brvm_web = None

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
    """Interroge l'IA Gemini en priorité. Utilise le dictionnaire local uniquement en cas de panne."""
    if not terme or not str(terme).strip():
        return ""

    terme_clean = str(terme).strip()
    terme_upper = terme_clean.upper()

    # 1. PRIORITÉ À L'IA GEMINI (Gère les pluriels, la casse et les phrases)
    model = get_gemini_model()
    if model:
        try:
            prompt = f"Explique le terme boursier ou financier '{terme_clean}' (contexte BRVM si pertinent) de manière concise en 2 phrases maximum."
            response = model.generate_content(prompt)
            return f"🤖 **{terme_clean}** :\n{response.text.strip()}"
        except Exception:
            pass  # En cas d'erreur de clé ou de réseau, bascule sur le dictionnaire local

    # 2. SECOURS (FALLBACK) SUR LE DICTIONNAIRE LOCAL
    # Recherche flexible (match partiel pour tolérer le pluriel)
    for cle, definition in LEXIQUE_FINANCIER.items():
        if cle in terme_upper or terme_upper in cle:
            return f"📚 **{cle} (Lexique local)** :\n{definition}"

    return f"💡 **{terme_clean}** : Service IA indisponible et terme inconnu du dictionnaire local."


# --- INITIALISATION BDD SQLITE ---
def init_tables_sqlite():
    """Initialise les tables SQLite sans altérer les données existantes."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS screening (
            Ticker TEXT PRIMARY KEY,
            Nom TEXT,
            "Cours (FCFA)" REAL,
            "Variation (%)" REAL,
            Volume INTEGER,
            date_maj TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date TEXT,
            cours REAL,
            volume INTEGER,
            UNIQUE(ticker, date) ON CONFLICT REPLACE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portefeuille (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            quantite INTEGER,
            prix_achat REAL,
            date_achat TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            ticker TEXT PRIMARY KEY,
            nom TEXT,
            secteur TEXT,
            cours_actuel REAL,
            dernier_dividende_net REAL,
            yield_net_pct REAL,
            date_detachement TEXT,
            date_paiement TEXT
        )
    """)

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

    for col, col_type in [
        ("date_grade", "TEXT"),
        ("prix_entree", "REAL DEFAULT 0"),
        ("prix_cible", "REAL DEFAULT 0"),
        ("stop_loss", "REAL DEFAULT 0"),
        ("prix_cloture", "REAL DEFAULT 0"),
    ]:
        try:
            cursor.execute(
                f"ALTER TABLE signaux_contrarians ADD COLUMN {col} {col_type}"
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


# --- FONCTIONS UTILITAIRES ---
def verifier_peremption_grade(grade, date_grade_str):
    if not grade or grade == "NE":
        return "NE (Non Évalué)", "gray", False

    if not date_grade_str:
        return f"Grade {grade} (Date inconnue)", "orange", True

    try:
        date_g = datetime.datetime.strptime(date_grade_str, "%Y-%m-%d").date()
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

    return pd.DataFrame(columns=[
        "Ticker",
        "Nom",
        "Cours (FCFA)",
        "Variation (%)",
        "Volume",
        "date_maj",
    ])


def charger_calendrier_dividendes():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(
            """
            SELECT 
                ticker AS Ticker,
                nom AS Nom,
                secteur AS Secteur,
                cours_actuel AS "Cours (FCFA)",
                dernier_dividende_net AS "Dividende Net (FCFA)",
                yield_net_pct AS "Yield Net (%)",
                date_detachement AS "Détachement",
                date_paiement AS "Paiement"
            FROM actions
            ORDER BY yield_net_pct DESC
        """,
            conn,
        )
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
        if not df.empty:
            return df
    except Exception:
        pass

    return pd.DataFrame(columns=["date", "cours", "volume"])


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
        "INSERT INTO portefeuille (ticker, quantite, prix_achat, date_achat)"
        " VALUES (?, ?, ?, ?)",
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


def charger_signaux_contrarians():
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(
            "SELECT * FROM signaux_contrarians ORDER BY date_signal DESC,"
            " ticker ASC",
            conn,
        )
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


def detecter_signaux_contrarians_auto(df_screening, financials_dict):
    signaux = []
    if df_screening.empty:
        return pd.DataFrame(signaux)

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
                "Élément ignoré par le marché": (
                    f"Repli de {var:.2f} % alors que le rendement du dividende"
                    f" ({rendement_div:.1f} %) est intact."
                ),
                "Risque principal": (
                    "Pression vendeuse résiduelle à court terme."
                ),
                "Conviction": "MOYENNE",
            })
        elif rendement_div >= 4.0 and -1.0 < var < 1.5:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Archétype": "Archétype 2 — Catalyseur négligé",
                "Élément ignoré par le marché": (
                    f"Dividende de {div:,.0f} FCFA ({rendement_div:.1f} %) à"
                    f" peine intégré par le cours ({var:+.2f} %)."
                ),
                "Risque principal": "Passivité du marché jusqu'au détachement.",
                "Conviction": "MOYENNE-FORTE",
            })
    return pd.DataFrame(signaux)


# --- DÉMARRAGE BASE DE DONNÉES ET DONNÉES ---
init_tables_sqlite()
df_screening = charger_donnees_screening()
financials_dict = fundamentals.charger_financials()


# --- BARRE LATÉRALE ---
st.sidebar.title("🎛️ Panneau de Contrôle")

st.sidebar.header("🔄 Synchronisation Web")
if st.sidebar.button("⚡ Actualiser les cours (Direct Web)"):
    if synchroniser_brvm_web:
        with st.spinner("Récupération des cours en direct..."):
            succes, msg = synchroniser_brvm_web()
            if succes:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)
    else:
        st.sidebar.error("Fichier `actualiser_donnees.py` non trouvé.")

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtres du Screener")

recherche_ticker = (
    st.sidebar.text_input("Rechercher un Ticker :", "").strip().upper()
)

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
    st.sidebar.slider(
        "Taux de frais SGI (%)",
        min_value=0.5,
        max_value=3.0,
        value=1.5,
        step=0.1,
    )
    / 100
)

st.sidebar.markdown("---")
st.sidebar.header("📖 Dictionnaire & Assistant IA")
mot_a_traduire = st.sidebar.text_input(
    "Rechercher la définition d'un terme :", placeholder="ex: PER, BPA, Graham..."
)
if mot_a_traduire:
    definition_trouvee = traduire_ou_expliquer_terme(mot_a_traduire)
    st.sidebar.info(definition_trouvee)

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


# --- EN-TÊTE ET ONGLETS PRINCIPAUX ---
st.title("📊 BRVM Quantum Analytics")

if (
    not df_screening.empty
    and "date_maj" in df_screening.columns
    and not df_screening["date_maj"].isna().all()
):
    derniere_maj = df_screening["date_maj"].iloc[0]
    st.info(
        "📅 **Dernière mise à jour du marché** — Cotations au :"
        f" **{derniere_maj}**"
    )
else:
    st.warning(
        "⚠️ Aucune donnée boursière dans SQLite (`brvm.db`). Cliquez sur"
        " **'Actualiser les cours'** dans le panneau latéral."
    )

with st.expander(
    "ℹ️ Résumé de la Méthodologie & Cadre de Décision (MBC-METH-2026-07-001)"
):
    st.markdown("""
    **BRVM Quantum Analytics** applique une discipline stricte en 5 piliers non négociables :
    1. **Valuation Value & Graham** : Sélection des titres présentant un score fondamental élevé et une marge de sécurité via le Nombre de Graham.
    2. **Traçabilité des Grades / Gate** : Attribution d'un Grade de Zone ($A, B, C, NE$) horodaté avec **règle de péremption stricte à 21 jours**.
    3. **Contrôle Strict des Risques & R:R** : Plafonds d'exposition ($\le 15\%$ par ligne / $\le 50\%$ par secteur) et validation du Ratio Gain/Risque.
    4. **Mémoire Longitudinal** : Suivi hebdomadaire des scores ($S_1, S_2, \dots$) pour anticiper l'essoufflement des fondamentaux.
    5. **Signaux Contrarians & Track-Record** : Détection automatique, suivi et mesure du Win-Rate réel des opportunités contrarians.
    """)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Screener & Graphiques",
    "📅 Calendrier Dividendes",
    "🧮 Simulateur & Risk R:R",
    "💼 Mon Portefeuille",
    "🔬 Analyse Fondamentale & Value",
    "⚡ Signaux Contrarians & Track-Record",
])

# --- ONGLET 1 : SCREENER ---
with tab1:
    if df_screening.empty:
        st.info(
            "Le tableau de bord affichera automatiquement les actions dès la"
            " première synchronisation web."
        )
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Actions Sélectionnées", f"{len(df_filtre)} / {len(df_screening)}"
        )
        k2.metric(
            "Hausses 📈",
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

        df_filtre.index = range(1, len(df_filtre) + 1)
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
        else:
            st.info(f"Aucun historique enregistré pour {ticker_choisi}.")

# --- ONGLET 2 : CALENDRIER DIVIDENDES ---
with tab2:
    st.subheader("📅 Calendrier des Dividendes & Rendements (Yield %)")
    df_div = charger_calendrier_dividendes()
    if df_div.empty:
        st.info(
            "Aucune donnée de dividendes enregistrée. Exécutez"
            " `remplir_donnees.py` pour alimenter cette table."
        )
    else:
        d1, d2, d3 = st.columns(3)
        d1.metric("Nombre de titres référencés", len(df_div))
        d2.metric("Rendement Net Max", f"{df_div['Yield Net (%)'].max():.2f} %")
        d3.metric("Rendement Net Moyen", f"{df_div['Yield Net (%)'].mean():.2f} %")

        st.markdown("---")
        st.dataframe(df_div, use_container_width=True)

# --- ONGLET 3 : SIMULATEUR & RISK R:R ---
with tab3:
    st.subheader("🧮 Simulateur de Rendement Net SGI & Risk/Reward")

    if df_screening.empty:
        st.info(
            "Alimentez la base de données pour charger les cours actuels."
        )
    else:
        # --- INPUTS STRUCTURÉS ---
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            action_simu = st.selectbox(
                "Action :", df_screening["Ticker"].unique(), key="sim_t"
            )
            cours_actuel = float(
                df_screening.loc[
                    df_screening["Ticker"] == action_simu, "Cours (FCFA)"
                ].values[0]
            )
        with c2:
            prix_achat = st.number_input(
                "Prix Achat (FCFA)", value=cours_actuel, step=50.0
            )
            quantite = st.number_input("Quantité", value=100, min_value=1)
        with c3:
            prix_vente = st.number_input(
                "Objectif Vente (FCFA)",
                value=float(round(cours_actuel * 1.1)),
                step=50.0,
            )
        with c4:
            stop_loss = st.number_input(
                "Stop Loss (FCFA)",
                value=float(round(cours_actuel * 0.95)),
                step=50.0,
            )

        # --- CALCULS FINANCIERS COMPLETS ---
        capital_brut = quantite * prix_achat
        frais_achat = capital_brut * taux_frais_sgi
        cout_total_achat = capital_brut + frais_achat

        # Vente Objectif
        prod_brut_vente = quantite * prix_vente
        frais_vente = prod_brut_vente * taux_frais_sgi
        prod_net_vente = prod_brut_vente - frais_vente
        gain_net = prod_net_vente - cout_total_achat
        roi_net = (
            (gain_net / cout_total_achat) * 100 if cout_total_achat > 0 else 0
        )

        # Stop Loss
        prod_brut_sl = quantite * stop_loss
        frais_sl = prod_brut_sl * taux_frais_sgi
        perte_nette = cout_total_achat - (prod_brut_sl - frais_sl)

        # Ratio Gain/Risque et Seuil de Rentrabilité
        ratio_rr = (gain_net / perte_nette) if perte_nette > 0 else 0.0
        breakeven = prix_achat * ((1 + taux_frais_sgi) / (1 - taux_frais_sgi))

        st.markdown("---")

        # --- BADGE DÉCISIONNEL AUTOMATIQUE ---
        if ratio_rr >= 2.0 and roi_net > 0:
            st.success(
                f"🟢 **EXCELLENT RISK/REWARD ({ratio_rr:.2f}:1)** — Ce trade offers"
                " un potentiel de gain largement supérieur au risque encouru."
            )
        elif ratio_rr >= 1.0 and roi_net > 0:
            st.warning(
                f"🟡 **RISQUE MODÉRÉ ({ratio_rr:.2f}:1)** — Le ratio gain/risque"
                " est passable. Recherchez un meilleur point d'entrée."
            )
        else:
            st.error(
                f"🔴 **TRADE DÉCONSEILLÉ ({ratio_rr:.2f}:1)** — Risque trop élevé"
                " par rapport au gain potentiel ou sous le seuil de"
                " rentabilité."
            )

        # --- KPIS PRINCIPAUX ---
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric(
            "Capital Investi",
            f"{cout_total_achat:,.0f} FCFA".replace(",", " "),
        )
        m2.metric(
            "Gain Net Cible",
            f"{gain_net:,.0f} FCFA".replace(",", " "),
            delta=f"{roi_net:+.2f}%",
        )
        m3.metric(
            "Perte Max (Stop)",
            f"-{perte_nette:,.0f} FCFA".replace(",", " "),
            delta=f"-{(perte_nette/cout_total_achat)*100:.2f}%",
            delta_color="inverse",
        )
        m4.metric("Ratio R:R", f"{ratio_rr:.2f} : 1")
        m5.metric(
            "Seuil Rentrabilité", f"{breakeven:,.0f} FCFA".replace(",", " ")
        )

        st.markdown("---")

        # --- SCÉNARIOS ET DÉTAILS D'EXÉCUTION ---
        col_t1, col_t2 = st.columns([1, 1])

        with col_t1:
            st.markdown("##### 🧾 Décomposition des Frais SGI")
            df_frais = pd.DataFrame([
                {
                    "Opération": "Achat",
                    "Montant Brut": f"{capital_brut:,.0f} FCFA".replace(
                        ",", " "
                    ),
                    "Frais SGI": f"{frais_achat:,.0f} FCFA".replace(",", " "),
                    "Total Net": f"{cout_total_achat:,.0f} FCFA".replace(
                        ",", " "
                    ),
                },
                {
                    "Opération": "Vente Cible",
                    "Montant Brut": f"{prod_brut_vente:,.0f} FCFA".replace(
                        ",", " "
                    ),
                    "Frais SGI": f"{frais_vente:,.0f} FCFA".replace(",", " "),
                    "Total Net": f"{prod_net_vente:,.0f} FCFA".replace(
                        ",", " "
                    ),
                },
            ])
            st.table(df_frais)

        with col_t2:
            st.markdown("##### 📊 Matrice de Sensibilité des Cours")
            scenarios = []
            for p_pct in [-0.05, 0.0, 0.03, 0.05, 0.10, 0.15]:
                p_sim = prix_achat * (1 + p_pct)
                p_net = (
                    quantite * p_sim
                ) * (1 - taux_frais_sgi) - cout_total_achat
                r_pct = (p_net / cout_total_achat) * 100
                scenarios.append({
                    "Variation Cours": f"{p_pct*100:+.1f}%",
                    "Prix Action": f"{p_sim:,.0f} FCFA".replace(",", " "),
                    "Gain/Perte Net": f"{p_net:,.0f} FCFA".replace(",", " "),
                    "ROI Net": f"{r_pct:+.2f}%",
                })
            st.dataframe(pd.DataFrame(scenarios), use_container_width=True)

import plotly.express as px

# --- ONGLET 4 : MON PORTEFEUILLE & AIDE À LA DÉCISION ---
with tab4:
    st.subheader("💼 Gestion & Analyse Décisionnelle du Portefeuille")

    # --- INITIALISATION AUTOMATIQUE & MIGRATION DE LA BASE SQL ---
    try:
        conn = sqlite3.connect("brvm.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portefeuille (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                quantite INTEGER,
                prix_achat REAL,
                pru_reel REAL,
                date_achat TEXT
            )
        """)
        # Vérification / Migration si la colonne pru_reel n'existait pas
        cursor.execute("PRAGMA table_info(portefeuille)")
        colonnes_existantes = [col[1] for col in cursor.fetchall()]
        if "pru_reel" not in colonnes_existantes:
            cursor.execute("ALTER TABLE portefeuille ADD COLUMN pru_reel REAL")
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erreur d'initialisation SQL : {e}")

    # --- SECTION 1 : AJOUT D'UNE LIGNE D'ACHAT ---
    with st.expander("➕ Ajouter / Enregistrer une Ligne d'Achat", expanded=False):
        with st.form("form_ajout_portefeuille"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ticker_p = st.selectbox("Action :", df_screening["Ticker"].unique(), key="port_t")
                cours_ref = float(df_screening.loc[df_screening["Ticker"] == ticker_p, "Cours (FCFA)"].values[0]) if not df_screening.empty else 1000.0
            with c2:
                qte_p = st.number_input("Quantité", min_value=1, value=50, step=1)
            with c3:
                prix_p = st.number_input("Prix d'Achat Unitaire (FCFA)", min_value=1.0, value=cours_ref, step=50.0)
            with c4:
                date_p = st.date_input("Date d'achat")

            btn_ajouter = st.form_submit_button("💾 Enregistrer dans le Portefeuille")

            if btn_ajouter:
                pru_reel = prix_p * (1 + taux_frais_sgi)
                try:
                    conn = sqlite3.connect("brvm.db")
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO portefeuille (ticker, quantite, prix_achat, pru_reel, date_achat) VALUES (?, ?, ?, ?, ?)",
                        (ticker_p, qte_p, prix_p, pru_reel, str(date_p))
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {qte_p} actions {ticker_p} ajoutées au portefeuille !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'enregistrement : {e}")

    # --- SECTION 2 : LECTURE ET CALCULS DU PORTEFEUILLE ---
    try:
        conn = sqlite3.connect("brvm.db")
        df_port = pd.read_sql("SELECT * FROM portefeuille", conn)
        conn.close()
    except Exception:
        df_port = pd.DataFrame()

    if df_port.empty:
        st.info("💡 Votre portefeuille est actuellement vide. Ajoutez vos premières lignes ci-dessus.")
    else:
        # Traitement pour les anciennes lignes où pru_reel était NULL
        df_port["pru_reel"] = df_port["pru_reel"].fillna(df_port["prix_achat"] * (1 + taux_frais_sgi))

        # Sélection sécurisée des colonnes de df_screening
        cols_merge = [c for c in ["Ticker", "Cours (FCFA)", "Secteur"] if c in df_screening.columns]

        # Fusion avec les cours actuels
        df_port_merged = df_port.merge(
            df_screening[cols_merge],
            left_on="ticker",
            right_on="Ticker",
            how="left"
        )
        df_port_merged["Cours (FCFA)"] = df_port_merged["Cours (FCFA)"].fillna(df_port_merged["prix_achat"])

        # Calculs Financiers par ligne
        df_port_merged["Capital Investi (FCFA)"] = df_port_merged["quantite"] * df_port_merged["pru_reel"]
        df_port_merged["Valeur Actuelle Nette (FCFA)"] = df_port_merged["quantite"] * df_port_merged["Cours (FCFA)"] * (1 - taux_frais_sgi)
        df_port_merged["Plus-Value Nette (FCFA)"] = df_port_merged["Valeur Actuelle Nette (FCFA)"] - df_port_merged["Capital Investi (FCFA)"]
        df_port_merged["Performance (%)"] = (df_port_merged["Plus-Value Nette (FCFA)"] / df_port_merged["Capital Investi (FCFA)"]) * 100

        # Totaux Portefeuille
        total_investi = df_port_merged["Capital Investi (FCFA)"].sum()
        total_valeur_nette = df_port_merged["Valeur Actuelle Nette (FCFA)"].sum()
        total_pv_nette = total_valeur_nette - total_investi
        perf_globale_pct = (total_pv_nette / total_investi * 100) if total_investi > 0 else 0.0

        df_port_merged["Poids (%)"] = (df_port_merged["Valeur Actuelle Nette (FCFA)"] / total_valeur_nette) * 100

        # Avis Décisionnel Suggéré
        def generer_avis(row):
            if row["Poids (%)"] > 25.0:
                return "⚠️ Alléger (Risque Concentration)"
            elif row["Performance (%)"] >= 20.0:
                return "🎯 Prise de Profit Partielle"
            elif row["Performance (%)"] <= -12.0:
                return "🚨 Niveau Stop Loss Atteint"
            else:
                return "🟢 Conserver"

        df_port_merged["Décision Suggérée"] = df_port_merged.apply(generer_avis, axis=1)

        st.markdown("---")

        # --- SECTION 3 : METRIQUES GLOBALES (KPIS) ---
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Capital Investi (avec PRU)", f"{total_investi:,.0f} FCFA".replace(",", " "))
        k2.metric("Valeur Actuelle Nette", f"{total_valeur_nette:,.0f} FCFA".replace(",", " "))
        k3.metric(
            "Plus/Moins-Value Latente",
            f"{total_pv_nette:+,.0f} FCFA".replace(",", " "),
            delta=f"{perf_globale_pct:+.2f}%"
        )

        lignes_surconcentrees = df_port_merged[df_port_merged["Poids (%)"] > 25.0]
        if not lignes_surconcentrees.empty:
            tickers_alert = ", ".join(lignes_surconcentrees["ticker"].tolist())
            k4.metric("Alerte Risque", "ÉLEVÉ", delta=f"Concentré sur {tickers_alert}", delta_color="inverse")
        else:
            k4.metric("Diversification", "OPTIMALE", delta="Aucune sur-exposition")

        st.markdown("---")

        # --- SECTION 4 : VISUALISATION ---
        col_g1, col_g2 = st.columns([1, 1])

        with col_g1:
            st.markdown("##### 🍩 Allocation par Action")
            fig_pie = px.pie(
                df_port_merged,
                names="ticker",
                values="Valeur Actuelle Nette (FCFA)",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(margin=dict(t=20, b=20, l=10, r=10), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_g2:
            st.markdown("##### 📊 Performance Nette par Ligne (%)")
            fig_bar = px.bar(
                df_port_merged,
                x="ticker",
                y="Performance (%)",
                color="Performance (%)",
                color_continuous_scale=["#EF553B", "#00CC96"],
                text_auto=".1f"
            )
            fig_bar.update_layout(margin=dict(t=20, b=20, l=10, r=10), yaxis_title="Performance %")
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- SECTION 5 : TABLEAU ET SUPPRESSION ---
        st.markdown("##### 📑 Détail des Positions & Recommandations")

        df_display = df_port_merged[[
            "id", "ticker", "quantite", "pru_reel", "Cours (FCFA)",
            "Capital Investi (FCFA)", "Valeur Actuelle Nette (FCFA)",
            "Plus-Value Nette (FCFA)", "Performance (%)", "Poids (%)", "Décision Suggérée"
        ]].copy()

        df_display["pru_reel"] = df_display["pru_reel"].apply(lambda x: f"{x:,.0f} FCFA".replace(",", " "))
        df_display["Cours (FCFA)"] = df_display["Cours (FCFA)"].apply(lambda x: f"{x:,.0f} FCFA".replace(",", " "))
        df_display["Capital Investi (FCFA)"] = df_display["Capital Investi (FCFA)"].apply(lambda x: f"{x:,.0f} FCFA".replace(",", " "))
        df_display["Valeur Actuelle Nette (FCFA)"] = df_display["Valeur Actuelle Nette (FCFA)"].apply(lambda x: f"{x:,.0f} FCFA".replace(",", " "))
        df_display["Plus-Value Nette (FCFA)"] = df_display["Plus-Value Nette (FCFA)"].apply(lambda x: f"{x:+,.0f} FCFA".replace(",", " "))
        df_display["Performance (%)"] = df_display["Performance (%)"].apply(lambda x: f"{x:+.2f}%")
        df_display["Poids (%)"] = df_display["Poids (%)"].apply(lambda x: f"{x:.1f}%")

        st.dataframe(df_display, use_container_width=True)

        with st.expander("🗑️ Vendre ou Supprimer une Ligne du Portefeuille"):
            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                id_to_delete = st.selectbox("Sélectionner l'ID de la ligne à supprimer :", df_port_merged["id"].tolist())
            with col_del2:
                st.write("")
                st.write("")
                if st.button("❌ Supprimer la ligne", type="primary"):
                    conn = sqlite3.connect("brvm.db")
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM portefeuille WHERE id = ?", (id_to_delete,))
                    conn.commit()
                    conn.close()
                    st.success(f"Ligne ID {id_to_delete} supprimée.")
                    st.rerun()

# --- ONGLET 5 : ANALYSE FONDAMENTALE ---
with tab5:
    st.subheader("🔬 Analyse Fondamentale & Valuation (Graham / Value)")
    if df_screening.empty:
        st.info("Aucune donnée chargée pour le moment.")
    else:
        ticker_fund = st.selectbox(
            "Sélectionner une action à analyser :",
            df_screening["Ticker"].unique(),
            key="fund_select",
        )
        cours_f = float(
            df_screening.loc[
                df_screening["Ticker"] == ticker_fund, "Cours (FCFA)"
            ].values[0]
        )

        fin = financials_dict.get(ticker_fund, {})
        bpa = float(fin.get("BPA", 0))
        vnc = float(fin.get("VNC", 0))
        per_db = float(fin.get("PER", 0))
        div = float(fin.get("Dividende", 0))

        # Calculs des métriques avancées
        nombre_graham = (22.5 * bpa * vnc) ** 0.5 if bpa > 0 and vnc > 0 else 0
        marge_securite = (
            ((nombre_graham - cours_f) / nombre_graham * 100)
            if nombre_graham > 0
            else 0
        )
        potentiel_hausse = (
            ((nombre_graham - cours_f) / cours_f * 100)
            if (nombre_graham > 0 and cours_f > 0)
            else 0
        )
        
        per_calcul = (cours_f / bpa) if bpa > 0 else per_db
        pbv_calcul = (cours_f / vnc) if vnc > 0 else 0
        yield_net = (div / cours_f * 100) if cours_f > 0 else 0

        # Logique du Signal Décisionnel
        if marge_securite >= 20 and yield_net >= 4.5:
            signal = "🟢 ACHAT FORT (Value Discount)"
        elif marge_securite > 0:
            signal = "🟡 CONSERVER / ACHAT MODÉRÉ"
        else:
            signal = "🔴 SURÉVALUÉ / VENDRE"

        # Affichage des métriques clés
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("Cours Actuel", f"{cours_f:,.0f} FCFA".replace(",", " "))
        f2.metric(
            "Nombre de Graham",
            f"{nombre_graham:,.0f} FCFA".replace(",", " ") if nombre_graham > 0 else "N/A",
        )
        f3.metric(
            "Marge de Sécurité",
            f"{marge_securite:+.1f}%" if nombre_graham > 0 else "N/A",
            delta=f"Upside: {potentiel_hausse:+.1f}%" if nombre_graham > 0 else None,
        )
        per_str = f"{per_calcul:.1f}x" if per_calcul > 0 else "N/A"
        pbv_str = f"{pbv_calcul:.2f}x" if pbv_calcul > 0 else "N/A"
        f4.metric("PER | P/BV", f"{per_str} | {pbv_str}")
        f5.metric("Yield Net", f"{yield_net:.2f} %")

        st.markdown(f"#### Recommandation de Décision : **{signal}**")

        # Synthèse des Piliers Fondamentaux
        st.markdown("##### 📊 Synthèse des Piliers Fondamentaux")
        tableau_aide = [
            {
                "Indicateur": "Bénéfice Par Action (BPA)",
                "Valeur": f"{bpa:,.0f} FCFA".replace(",", " ") if bpa > 0 else "N/A",
                "Seuil de Sécurité": "> 0 FCFA",
                "Analyse": "Bénéfice net positif" if bpa > 0 else "Nécessite rentabilité",
            },
            {
                "Indicateur": "Valeur Comptable (VNC / BV)",
                "Valeur": f"{vnc:,.0f} FCFA".replace(",", " ") if vnc > 0 else "N/A",
                "Seuil de Sécurité": "P/BV < 1.0x",
                "Analyse": "Côte sous fonds propres" if (pbv_calcul > 0 and pbv_calcul < 1) else ("Surcote sur fonds propres" if pbv_calcul >= 1 else "Non évalué"),
            },
            {
                "Indicateur": "Rendement Dividende Net",
                "Valeur": f"{yield_net:.2f} %",
                "Seuil de Sécurité": "> 5.0 %",
                "Analyse": "Rendement attractif" if yield_net >= 5 else "Rendement modéré",
            },
            {
                "Indicateur": "Potentiel de Hausse Théorique",
                "Valeur": f"+{potentiel_hausse:.1f} %" if nombre_graham > 0 else "N/A",
                "Seuil de Sécurité": "> +25.0 %",
                "Analyse": "Objectif de cours théorique de Graham",
            },
        ]
        st.table(tableau_aide)

        st.markdown("---")
        st.markdown("### 📝 Saisie du Suivi Hebdomadaire (Memory Gate)")
        with st.form(key=f"form_suivi_{ticker_fund}"):
            c_s1, c_s2, c_s3 = st.columns(3)
            with c_s1:
                semaine_input = st.text_input(
                    "Semaine (ex: 2026-W37)",
                    value=datetime.date.today().strftime("%Y-W%W"),
                )
                score_input = st.number_input(
                    "Score Fondamental (0 à 10)",
                    min_value=0.0,
                    max_value=10.0,
                    value=7.0,
                    step=0.5,
                )
            with c_s2:
                grade_input = st.selectbox(
                    "Grade de Zone", ["NE", "A", "B", "C"]
                )
                date_grade_input = st.date_input(
                    "Date d'attribution du Grade", datetime.date.today()
                )
            with c_s3:
                ratio_liq_input = st.number_input(
                    "Ratio de Liquidité", min_value=0.0, value=1.0, step=0.1
                )
                commentaire_input = st.text_area(
                    "Commentaire / Observation", value="", height=68
                )

            btn_save_suivi = st.form_submit_button(
                "💾 Enregistrer le Suivi Weekly"
            )

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
                st.success(
                    f"Suivi hebdomadaire enregistré pour {ticker_fund} !"
                )
                st.rerun()

        st.markdown("---")
        st.markdown("### 📋 Historique des Suivis Enregistrés")
        df_suivi = charger_suivi_longitudinal()
        if not df_suivi.empty:
            st.dataframe(df_suivi, use_container_width=True)
        else:
            st.info("Aucun historique de suivi enregistré.")

# --- FONCTION DE DÉTECTION CONTRARIAN ENRICHIE ---
def detecter_signaux_contrarians_auto(df_screening, financials_dict):
    signaux = []
    if df_screening.empty:
        return pd.DataFrame(signaux)

    for _, row in df_screening.iterrows():
        ticker = row.get("Ticker")
        cours = float(row.get("Cours (FCFA)", 0))
        var = float(row.get("Variation (%)", 0))

        if cours <= 0:
            continue

        fin = financials_dict.get(ticker, {})
        div = float(fin.get("Dividende", 0))
        bpa = float(fin.get("BPA", 0))
        vnc = float(fin.get("VNC", 0))

        rendement_div = (div / cours * 100) if cours > 0 else 0

        # Calcul du Prix Cible (Nombre de Graham si valide, sinon +20%)
        graham = (22.5 * bpa * vnc) ** 0.5 if (bpa > 0 and vnc > 0) else 0
        prix_cible = round(graham, 0) if graham > cours else round(cours * 1.20, 0)

        # Calcul du Stop-Loss de sécurité (-7%)
        stop_loss = round(cours * 0.93, 0)

        # Ratios de Risque / Gain
        risque = cours - stop_loss
        gain = prix_cible - cours
        ratio_rr = (gain / risque) if risque > 0 else 0
        potentiel = ((prix_cible - cours) / cours * 100) if cours > 0 else 0

        archetype = None
        element_ignore = ""
        risque_principal = ""
        conviction = ""
        action = ""

        # Archétype 1 : Sur-réaction négative
        if var <= -1.0 and rendement_div >= 4.5:
            archetype = "Archétype 1 — Sur-réaction négative"
            element_ignore = f"Repli de {var:.2f} % alors que le rendement du dividende ({rendement_div:.1f} %) est intact."
            risque_principal = "Pression vendeuse résiduelle à court terme."
            conviction = "🟢 FORTE" if ratio_rr >= 2.5 else "🟡 MOYENNE"
            action = "⚡ ACHAT CONTRARIAN" if ratio_rr >= 2.5 else "👀 À SURVEILLER"

        # Archétype 2 : Catalyseur négligé
        elif rendement_div >= 4.0 and -1.0 < var < 1.5:
            archetype = "Archétype 2 — Catalyseur négligé"
            element_ignore = f"Dividende de {div:,.0f} FCFA ({rendement_div:.1f} %) non intégré par le cours ({var:+.2f} %)."
            risque_principal = "Passivité du marché jusqu'au détachement."
            conviction = "🟢 FORTE" if ratio_rr >= 2.0 else "🟡 MOYENNE"
            action = "⚡ ACCUMULER" if ratio_rr >= 2.0 else "👀 OBSERVER"

        if archetype:
            signaux.append({
                "Ticker": ticker,
                "Nom": fin.get("Nom", ticker),
                "Action": action,
                "Conviction": conviction,
                "Cours (FCFA)": f"{cours:,.0f}".replace(",", " "),
                "Prix Cible": f"{prix_cible:,.0f}".replace(",", " "),
                "Stop-Loss": f"{stop_loss:,.0f}".replace(",", " "),
                "R:R": f"1 : {ratio_rr:.1f}",
                "Potentiel": f"+{potentiel:.1f}%",
                "Yield Net": f"{rendement_div:.1f}%",
                "Archétype": archetype,
                "Élément ignoré par le marché": element_ignore,
                "Risque principal": risque_principal,
            })

    return pd.DataFrame(signaux)


# --- ONGLET 6 COMPLÉTÉ : SIGNAUX CONTRARIANS ---
with tab6:
    st.subheader("⚡ Détection & Track-Record des Signaux Contrarians")

    df_auto = detecter_signaux_contrarians_auto(df_screening, financials_dict)

    if not df_auto.empty:
        # Cartes d'indicateurs synthétiques
        nb_fortes = len(df_auto[df_auto["Conviction"].str.contains("FORTE")])
        nb_achats = len(df_auto[df_auto["Action"].str.contains("ACHAT|ACCUMULER")])

        k1, k2, k3 = st.columns(3)
        k1.metric("Signaux Détectés", f"{len(df_auto)} Titres")
        k2.metric("Haute Conviction 🟢", f"{nb_fortes} Opportunités")
        k3.metric("Actions Recommandées ⚡", f"{nb_achats} Titres")

        st.markdown("---")
        st.markdown("##### 🔍 Signaux Détectés Automatiquement (Séance du jour)")

        cols_ordre = [
            "Ticker",
            "Action",
            "Conviction",
            "Cours (FCFA)",
            "Prix Cible",
            "Stop-Loss",
            "R:R",
            "Potentiel",
            "Yield Net",
            "Archétype",
            "Élément ignoré par le marché",
            "Risque principal",
        ]

        st.dataframe(df_auto[cols_ordre], use_container_width=True)
    else:
        st.info("💡 Aucun signal contrarian automatique détecté pour la séance actuelle.")

    st.markdown("---")
    st.markdown("##### 📜 Historique & Track-Record des Signaux (Base SQLite)")
    df_sig_db = charger_signaux_contrarians()
    if not df_sig_db.empty:
        st.dataframe(df_sig_db, use_container_width=True)
    else:
        st.info("Aucun signal historique enregistré en base de données.")