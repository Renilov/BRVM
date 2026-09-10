import streamlit as st
import pandas as pd
import numpy as np

# ==============================================================================
# 1. CONFIGURATION DE LA PAGE
# ==============================================================================
st.set_page_config(
    page_title="BRVM Quantum Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. LEXIQUE & FONCTIONS D'AIDE ET TOOLTIPS (HTML/CSS CUSTOM)
# ==============================================================================
LEXIQUE_ENFANT = {
    "BRVM": "Bourse Régionale des Valeurs Mobilières : le marché d'Afrique de l'Ouest où s'achètent et se vendent les actions.",
    "Graham": "Benjamin Graham : le père de l'analyse fondamentale qui cherchait les entreprises solides vendues sous leur vraie valeur.",
    "SGI": "Société de Gestion et d'Intermédiation : le courtier agréé obligatoire pour passer tes ordres en bourse.",
    "Contrarian": "Une stratégie d'investissement qui consiste à acheter quand tout le monde panique et vendre quand tout le monde s'emballe.",
    "PER": "Price Earnings Ratio : indique combien d'années de bénéfices tu payes d'avance en achetant l'action.",
    "Dividende": "La part des bénéfices de l'entreprise versée directement en argent aux actionnaires.",
    "Scraper": "Un programme informatique automatique qui collecte les cours de bourse sur internet.",
    "Grade": "Une note de santé et de solidité attribuée à une entreprise (ex: A, B, C).",
    "Liquidation / Dérating": "Chute brutale du prix d'une action lorsque les investisseurs s'en désintéressent massivement.",
    "Valuation Value": "L'estimation de la valeur réelle d'une entreprise basée sur ses actifs et ses bénéfices.",
    "Bénéfice Net": "L'argent réel qui reste à l'entreprise une fois toutes les factures, salaires et impôts payés."
}

# CSS pour créer des bulles d'explication élégantes au survol de la souris
STYLING_CSS = """
<style>
.tooltip {
  position: relative;
  display: inline-block;
  border-bottom: 2px dashed #007bff;
  color: #007bff;
  font-weight: 600;
  cursor: help;
}

.tooltip .tooltiptext {
  visibility: hidden;
  width: 250px;
  background-color: #1e293b;
  color: #ffffff;
  text-align: left;
  border-radius: 8px;
  padding: 10px 12px;
  position: absolute;
  z-index: 1000;
  bottom: 125%;
  left: 50%;
  margin-left: -125px;
  opacity: 0;
  transition: opacity 0.3s;
  font-size: 0.82rem;
  font-weight: normal;
  line-height: 1.4;
  box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.3);
}

.tooltip .tooltiptext::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: #1e293b transparent transparent transparent;
}

.tooltip:hover .tooltiptext {
  visibility: visible;
  opacity: 1;
}
</style>
"""
st.markdown(STYLING_CSS, unsafe_allow_html=True)


def bulle(mot: str, texte_affiche: str = None) -> str:
    """
    Génère le code HTML d'un mot avec bulle d'explication au survol.
    """
    definition = LEXIQUE_ENFANT.get(mot, "Définition non renseignée.")
    label = texte_affiche if texte_affiche else mot
    return f'<div class="tooltip">{label}<span class="tooltiptext">💡 <b>{mot}</b> : {definition}</span></div>'


# ==============================================================================
# 3. DONNÉES SIMULÉES POUR DÉMONSTRATION
# ==============================================================================
@st.cache_data
def load_data():
    data = {
        "Symbole": ["SNTS", "SGBC", "ETIT", "PALC", "ONTBF"],
        "Société": ["Sonatel", "Société Générale CI", "Ecobank", "Palmci", "ONATEL BF"],
        "Secteur": ["Télécoms", "Finances", "Finances", "Agriculture", "Télécoms"],
        "Prix (FCFA)": [17500, 16200, 19, 6800, 2250],
        "PER": [8.2, 6.5, 3.1, 4.8, 7.0],
        "Rendement (%)": [9.1, 8.5, 5.0, 12.3, 10.2],
        "Grade": ["A+", "A", "B", "B+", "A-"]
    }
    return pd.DataFrame(data)

df_actions = load_data()

# ==============================================================================
# 4. BARRE LATÉRALE (SIDEBAR)
# ==============================================================================
st.sidebar.title("⚙️ Configuration")

st.sidebar.subheader("Frais & Paramètres")
taux_sgi = st.sidebar.slider(
    "Taux de frais SGI (%)",
    min_value=0.5,
    max_value=3.0,
    value=1.5,
    step=0.1,
    help=LEXIQUE_ENFANT["SGI"]
)

secteur_filtre = st.sidebar.multiselect(
    "Filtrer par secteur",
    options=df_actions["Secteur"].unique(),
    default=df_actions["Secteur"].unique()
)

st.sidebar.divider()
st.sidebar.info("💡 **Astuce** : Survolez les mots soulignés en bleu dans l'application pour afficher les explications simplifiées.")

# ==============================================================================
# 5. EN-TÊTE ET EXPANDER MÉTHODOLOGIQUE
# ==============================================================================
st.title("📈 BRVM Quantum Analytics")
st.caption("Plateforme d'analyse décisionnelle et de scoring fondamental pour la BRVM")

with st.expander("ℹ️ Résumé de la Méthodologie & Cadre de Décision"):
    st.markdown(f"""
    **BRVM Quantum Analytics** applique une discipline d'investissement stricte basée sur 5 piliers :
    
    1. **{bulle('Valuation Value')} & {bulle('Graham')}** : Recherche d'entreprises de qualité sous-évaluées par le marché.
    2. **Système de {bulle('Grade', 'Grades')}** : Attribution d'une note synthétique globale basée sur la santé financière.
    3. **Rendement en {bulle('Dividende', 'Dividendes')}** : Sélection prioritaire des sociétés générant des flux de trésorerie distribuables.
    4. **Détection des Signaux {bulle('Contrarian', 'Contrarians')}** : Repérage des opportunités lors des phases de {bulle('Liquidation / Dérating', 'dérating massif')}.
    5. **Exécution via {bulle('SGI')}** : Prise en compte rigoureuse des frais d'intermédiation dans les calculs de rendement net.
    """, unsafe_allow_html=True)

st.divider()

# ==============================================================================
# 6. ONGLETS PRINCIPAUX
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["📊 Vue Générale", "🎯 Opportunités & Signaux", "📖 Dictionnaire & Lexique"])

# --- TAB 1 : VUE GÉNÉRALE ---
with tab1:
    st.subheader("Indicateurs Clés de Marché")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Actions Analysées", len(df_actions))
    col2.metric("PER Moyen", f"{df_actions['PER'].mean():.1f}x")
    col3.metric("Rendement Moyen", f"{df_actions['Rendement (%)'].mean():.1f}%")
    col4.metric("Frais SGI Appliqués", f"{taux_sgi}%")

    st.subheader("Tableau de Scoring des Actions")
    
    # Filtrage des données
    df_filtered = df_actions[df_actions["Secteur"].isin(secteur_filtre)]
    
    st.dataframe(
        df_filtered,
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown(f"""
    *Note : Le {bulle('PER')} et le rendement affichés sont bruts. Consultez votre {bulle('SGI')} pour connaître le rendement exact net d'impôts et de frais.*
    """, unsafe_allow_html=True)

# --- TAB 2 : OPPORTUNITÉS & SIGNAUX ---
with tab2:
    st.subheader("Détection des opportunités d'achat")
    
    st.markdown(f"""
    Cette section identifie les valeurs en situation de **{bulle('Liquidation / Dérating')}** temporaire,
    offrant un point d'entrée attractif selon les principes de la méthode **{bulle('Graham')}**.
    """, unsafe_allow_html=True)
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown(f"### 🛡️ Profil Défensif ({bulle('Dividende', 'Forts Dividendes')})")
        top_div = df_actions.sort_values(by="Rendement (%)", ascending=False).head(3)
        for _, row in top_div.iterrows():
            st.success(f"**{row['Société']} ({row['Symbole']})** — Rendement: **{row['Rendement (%)']}%** | Grade: **{row['Grade']}**")

    with col_right:
        st.markdown(f"### 🚀 Profil Décoté ({bulle('PER', 'Bas PER')})")
        top_val = df_actions.sort_values(by="PER", ascending=True).head(3)
        for _, row in top_val.iterrows():
            st.info(f"**{row['Société']} ({row['Symbole']})** — PER: **{row['PER']}x** | Grade: **{row['Grade']}**")

# --- TAB 3 : DICTIONNAIRE & LEXIQUE ---
with tab3:
    st.subheader("📚 Lexique des Termes Boursiers")
    st.write("Retrouvez ici toutes les définitions simplifiées utilisées dans la plateforme.")
    
    recherche = st.text_input("🔍 Rechercher un terme...", "")
    
    for terme, defn in LEXIQUE_ENFANT.items():
        if recherche.lower() in terme.lower() or recherche.lower() in defn.lower():
            with st.container():
                st.markdown(f"**{terme}**")
                st.write(defn)
                st.divider()

# ==============================================================================
# 7. PIED DE PAGE
# ==============================================================================
st.caption("BRVM Quantum Analytics © 2026 — Document généré pour analyse interne.")