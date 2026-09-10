import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

# 1. Configuration de la page Streamlit
st.set_page_config(
    page_title="BRVM Quantum Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS personnalisé
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F3F4F6;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #2563EB;
    }
</style>
""", unsafe_allow_html=True)


# 2. Fonction de chargement des données avec gestion du cache et sécurités
@st.cache_data(ttl=300)
def charger_donnees_reelles():
    db_paths = ["data/brvm.db", "brvm.db", "data/brvm_data.db"]
    df = None

    # Tentative de lecture dans SQLite
    for path in db_paths:
        if os.path.exists(path):
            try:
                conn = sqlite3.connect(path)
                # Vérifier les tables disponibles
                tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table';", conn)['name'].tolist()
                
                target_table = None
                for t in ['screening', 'cours', 'actions']:
                    if t in tables:
                        target_table = t
                        break
                
                if target_table:
                    df = pd.read_sql(f"SELECT * FROM {target_table}", conn)
                    conn.close()
                    if not df.empty:
                        break
                conn.close()
            except Exception:
                pass

    # Si aucune donnée n'a été lue, charger les données de secours (fallback)
    if df is None or df.empty:
        data_fallback = [
            {"Ticker": "SNTS", "Nom": "SONATEL SN", "Secteur": "Services Publics", "Cours (FCFA)": 21500, "Variation (%)": 0.50, "PER (x)": 7.8, "Rendement (%)": 6.98, "Dividende Net": 1500, "Détachement Coupon": "15/05/2026", "Paiement Effectif": "28/05/2026"},
            {"Ticker": "ORAC", "Nom": "ORAGROUP TOGO", "Secteur": "Finances", "Cours (FCFA)": 12800, "Variation (%)": -0.20, "PER (x)": 9.2, "Rendement (%)": 11.72, "Dividende Net": 1500, "Détachement Coupon": "02/06/2026", "Paiement Effectif": "16/06/2026"},
            {"Ticker": "SGBC", "Nom": "SOCIETE GENERALE CI", "Secteur": "Finances", "Cours (FCFA)": 19500, "Variation (%)": 1.20, "PER (x)": 6.5, "Rendement (%)": 10.77, "Dividende Net": 2100, "Détachement Coupon": "12/07/2026", "Paiement Effectif": "26/07/2026"},
            {"Ticker": "BOAB", "Nom": "BANK OF AFRICA BENIN", "Secteur": "Finances", "Cours (FCFA)": 10200, "Variation (%)": -0.78, "PER (x)": 7.2, "Rendement (%)": 7.35, "Dividende Net": 750, "Détachement Coupon": "14/05/2026", "Paiement Effectif": "28/05/2026"},
            {"Ticker": "BOABF", "Nom": "BANK OF AFRICA BF", "Secteur": "Finances", "Cours (FCFA)": 8990, "Variation (%)": 0.45, "PER (x)": 6.9, "Rendement (%)": 8.90, "Dividende Net": 800, "Détachement Coupon": "10/05/2026", "Paiement Effectif": "24/05/2026"},
            {"Ticker": "PALC", "Nom": "PALM CI", "Secteur": "Agriculture", "Cours (FCFA)": 6800, "Variation (%)": 2.10, "PER (x)": 5.4, "Rendement (%)": 12.50, "Dividende Net": 850, "Détachement Coupon": "20/06/2026", "Paiement Effectif": "05/07/2026"},
            {"Ticker": "ETIT", "Nom": "ECOBANK TRANS. INC.", "Secteur": "Finances", "Cours (FCFA)": 19, "Variation (%)": 0.00, "PER (x)": 4.1, "Rendement (%)": 8.00, "Dividende Net": 1.5, "Détachement Coupon": "30/05/2026", "Paiement Effectif": "15/06/2026"},
            {"Ticker": "TTLC", "Nom": "TOTAL CI", "Secteur": "Distribution", "Cours (FCFA)": 2400, "Variation (%)": -0.41, "PER (x)": 10.1, "Rendement (%)": 9.15, "Dividende Net": 220, "Détachement Coupon": "18/06/2026", "Paiement Effectif": "02/07/2026"}
        ]
        df = pd.DataFrame(data_fallback)

    # Nettoyage des types numériques pour éviter les erreurs de calcul
    cols_numeriques = ["Cours (FCFA)", "Variation (%)", "PER (x)", "Rendement (%)", "Dividende Net"]
    for col in cols_numeriques:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace("%", "").str.replace("FCFA", "").str.strip(), errors="coerce")

    return df


# 3. Chargement initial des données
df_raw = charger_donnees_reelles()

# 4. En-tête de l'application
st.markdown('<div class="main-title">📈 BRVM Quantum Analytics & Screener</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Analyse en temps réel de la Bourse Régionale des Valeurs Mobilières (UEMOA)</div>', unsafe_allow_html=True)

# 5. Barre latérale (Filtres)
st.sidebar.header("🔍 Filtres du Screener")

if st.sidebar.button("🔄 Rafraîchir les données"):
    st.cache_data.clear()
    st.rerun()

recherche_ticker = st.sidebar.text_input("Rechercher une action (Ticker ou Nom)", "").upper()

per_max = st.sidebar.slider(
    "PER Maximum (Valorisation)",
    min_value=0.0,
    max_value=30.0,
    value=20.0,
    step=0.5
)

rendement_min = st.sidebar.slider(
    "Rendement du Dividende Min (%)",
    min_value=0.0,
    max_value=20.0,
    value=0.0,
    step=0.5
)

secteurs_dispos = df_raw["Secteur"].dropna().unique().tolist() if "Secteur" in df_raw.columns else []
secteurs_selectionnes = st.sidebar.multiselect("Secteurs d'activité", options=secteurs_dispos, default=secteurs_dispos)

# Filtrage du DataFrame
df_filtered = df_raw.copy()

if recherche_ticker:
    df_filtered = df_filtered[
        df_filtered["Ticker"].str.contains(recherche_ticker, na=False) |
        (df_filtered["Nom"].str.contains(recherche_ticker, case=False, na=False) if "Nom" in df_filtered.columns else False)
    ]

if "PER (x)" in df_filtered.columns:
    df_filtered = df_filtered[(df_filtered["PER (x)"].isna()) | (df_filtered["PER (x)"] <= per_max)]

if "Rendement (%)" in df_filtered.columns:
    df_filtered = df_filtered[(df_filtered["Rendement (%)"].isna()) | (df_filtered["Rendement (%)"] >= rendement_min)]

if "Secteur" in df_filtered.columns and secteurs_selectionnes:
    df_filtered = df_filtered[df_filtered["Secteur"].isin(secteurs_selectionnes)]

# 6. Indicateurs Clés (KPIs)
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Actions analysées", len(df_filtered))

with col2:
    per_moyen = df_filtered["PER (x)"].mean() if "PER (x)" in df_filtered.columns else 0
    st.metric("PER Moyen", f"{per_moyen:.1f}x" if pd.notna(per_moyen) else "N/A")

with col3:
    rendement_moyen = df_filtered["Rendement (%)"].mean() if "Rendement (%)" in df_filtered.columns else 0
    st.metric("Rendement Moyen", f"{rendement_moyen:.2f} %" if pd.notna(rendement_moyen) else "N/A")

with col4:
    if "Variation (%)" in df_filtered.columns and not df_filtered.empty:
        top_gainer = df_filtered.loc[df_filtered["Variation (%)"].idxmax()]
        st.metric("Plus forte hausse", f"{top_gainer['Ticker']}", f"+{top_gainer['Variation (%)']:.2f}%")
    else:
        st.metric("Plus forte hausse", "N/A")

st.markdown("---")

# 7. Onglets principaux
tab_screener, tab_charts, tab_simulator = st.tabs(["📊 Screener & Opportunités", "📈 Graphiques & Comparatifs", "🧮 Simulateur de Dividendes"])

# Onglet 1 : Tableau d'Analyse
with tab_screener:
    st.subheader("Tableau de Screening BRVM")
    
    # Formatage de l'affichage
    st.dataframe(
        df_filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cours (FCFA)": st.column_config.NumberColumn(format="%d FCFA"),
            "Variation (%)": st.column_config.NumberColumn(format="%.2f %%"),
            "PER (x)": st.column_config.NumberColumn(format="%.1f x"),
            "Rendement (%)": st.column_config.NumberColumn(format="%.2f %%"),
            "Dividende Net": st.column_config.NumberColumn(format="%d FCFA"),
        }
    )

# Onglet 2 : Graphiques Interactifs
with tab_charts:
    st.subheader("Analyse Graphique des Valeurs")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if "PER (x)" in df_filtered.columns and "Rendement (%)" in df_filtered.columns:
            fig_scatter = px.scatter(
                df_filtered.dropna(subset=["PER (x)", "Rendement (%)"]),
                x="PER (x)",
                y="Rendement (%)",
                text="Ticker",
                size="Cours (FCFA)" if "Cours (FCFA)" in df_filtered.columns else None,
                color="Secteur" if "Secteur" in df_filtered.columns else None,
                title="Sélecteur d'opportunités : PER vs Rendement",
                labels={"PER (x)": "PER (Moins cher ➔)", "Rendement (%)": "Rendement % (Plus élevé ➔)"}
            )
            fig_scatter.update_traces(textposition='top center')
            st.plotly_chart(fig_scatter, use_container_width=True)
            
    with col_chart2:
        if "Rendement (%)" in df_filtered.columns:
            df_top_div = df_filtered.sort_values(by="Rendement (%)", ascending=False).head(10)
            fig_bar = px.bar(
                df_top_div,
                x="Ticker",
                y="Rendement (%)",
                title="Top 10 des Actions à fort Rendement (%)",
                color="Rendement (%)",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

# Onglet 3 : Simulateur de Portefeuille
with tab_simulator:
    st.subheader("Simulateur d'Investissement & Revenus passifs")
    
    col_sim1, col_sim2 = st.columns([1, 2])
    
    with col_sim1:
        action_choisie = st.selectbox("Choisir une action", options=df_raw["Ticker"].unique())
        montant_investi = st.number_input("Montant à investir (FCFA)", min_value=10000, value=1000000, step=50000)
        
        row_action = df_raw[df_raw["Ticker"] == action_choisie].iloc[0]
        cours = row_action.get("Cours (FCFA)", 0)
        rendement = row_action.get("Rendement (%)", 0)
        div_net = row_action.get("Dividende Net", 0)
        
    with col_sim2:
        if cours > 0:
            nb_titres = int(montant_investi // cours)
            invest_reel = nb_titres * cours
            reliquat = montant_investi - invest_reel
            revenu_annuel = nb_titres * div_net if div_net else (invest_reel * (rendement / 100))
            
            st.success(f"### Résultats de la simulation pour **{action_choisie}**")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Nombre de Titres", f"{nb_titres:,} actions")
            c2.metric("Montant Investi", f"{invest_reel:,.0f} FCFA")
            c3.metric("Revenu Annuel Estimé", f"{revenu_annuel:,.0f} FCFA", delta=f"{rendement:.2f}% / an")
            
            st.info(f"💡 Reliquat non investi : **{reliquat:,.0f} FCFA**")
        else:
            st.warning("Informations de cours indisponibles pour cette action.")

# Pied de page
st.markdown("---")
st.caption("BRVM Quantum Analytics • Données mises à jour automatiquement via GitHub Actions & Scraper.")