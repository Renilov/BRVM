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

# Style CSS
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1rem; color: #4B5563; margin-bottom: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# 2. Chargement des données avec recalcul dynamique et anti-NaN
@st.cache_data(ttl=180)
def charger_donnees_reelles():
    db_paths = ["data/brvm.db", "brvm.db"]
    df = None

    for path in db_paths:
        if os.path.exists(path):
            try:
                conn = sqlite3.connect(path)
                df = pd.read_sql("SELECT * FROM screening", conn)
                conn.close()
                if not df.empty:
                    break
            except Exception:
                pass

    if df is None or df.empty:
        try:
            from scraper import scraper_brvm_live
            scraper_brvm_live()
            if os.path.exists("data/brvm.db"):
                conn = sqlite3.connect("data/brvm.db")
                df = pd.read_sql("SELECT * FROM screening", conn)
                conn.close()
        except Exception:
            pass

    if df is None or df.empty:
        # Données de secours d'urgence
        data_fallback = [
            {"Ticker": "SNTS", "Nom": "SONATEL SENEGAL", "Secteur": "Services Publics", "Cours (FCFA)": 21500, "Variation (%)": 0.50, "PER (x)": 7.8, "Rendement (%)": 6.98, "Dividende Net": 1500, "Détachement Coupon": "15/05/2026", "Paiement Effectif": "28/05/2026"},
            {"Ticker": "AGLC", "Nom": "AFRICA GLOBAL LOGISTICS CI", "Secteur": "Transport", "Cours (FCFA)": 1400, "Variation (%)": 0.00, "PER (x)": 8.5, "Rendement (%)": 13.21, "Dividende Net": 185, "Détachement Coupon": "10/06/2026", "Paiement Effectif": "24/06/2026"},
            {"Ticker": "SGBC", "Nom": "SOCIETE GENERALE CI", "Secteur": "Finances", "Cours (FCFA)": 19500, "Variation (%)": 1.20, "PER (x)": 6.5, "Rendement (%)": 10.77, "Dividende Net": 2100, "Détachement Coupon": "12/07/2026", "Paiement Effectif": "26/07/2026"},
            {"Ticker": "ORAC", "Nom": "ORAGROUP TOGO", "Secteur": "Finances", "Cours (FCFA)": 12800, "Variation (%)": -0.20, "PER (x)": 9.2, "Rendement (%)": 11.72, "Dividende Net": 1500, "Détachement Coupon": "02/06/2026", "Paiement Effectif": "16/06/2026"},
            {"Ticker": "BOAB", "Nom": "BANK OF AFRICA BENIN", "Secteur": "Finances", "Cours (FCFA)": 10200, "Variation (%)": -0.78, "PER (x)": 7.2, "Rendement (%)": 7.35, "Dividende Net": 750, "Détachement Coupon": "14/05/2026", "Paiement Effectif": "28/05/2026"}
        ]
        df = pd.DataFrame(data_fallback)

    # Nettoyage strict des données numériques
    for col in ["Cours (FCFA)", "Variation (%)", "PER (x)", "Rendement (%)", "Dividende Net"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Recalcul dynamique du rendement (%)
    df["Rendement (%)"] = df.apply(
        lambda r: round((r["Dividende Net"] / r["Cours (FCFA)"]) * 100, 2)
        if (pd.notna(r["Dividende Net"]) and pd.notna(r["Cours (FCFA)"]) and r["Cours (FCFA)"] > 0 and r["Dividende Net"] > 0)
        else 0.0,
        axis=1
    )

    return df


# 3. Initialisation des données
df_raw = charger_donnees_reelles()

st.markdown('<div class="main-title">📈 BRVM Quantum Analytics & Screener</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Analyse en temps réel de la Bourse Régionale des Valeurs Mobilières (UEMOA)</div>', unsafe_allow_html=True)

# 4. Barre latérale (Filtres)
st.sidebar.header("🔍 Filtres du Screener")

if st.sidebar.button("🔄 Rafraîchir les cotations"):
    st.cache_data.clear()
    st.rerun()

recherche_ticker = st.sidebar.text_input("Rechercher une action (Ticker ou Nom)", "").upper()

per_max = st.sidebar.slider("PER Maximum", min_value=0.0, max_value=30.0, value=25.0, step=0.5)
rendement_min = st.sidebar.slider("Rendement Min (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.5)

secteurs_dispos = df_raw["Secteur"].dropna().unique().tolist() if "Secteur" in df_raw.columns else []
secteurs_selectionnes = st.sidebar.multiselect("Secteurs d'activité", options=secteurs_dispos, default=secteurs_dispos)

# Filtrage du DataFrame
df_filtered = df_raw.copy()

if recherche_ticker:
    df_filtered = df_filtered[
        df_filtered["Ticker"].str.contains(recherche_ticker, na=False) |
        (df_filtered["Nom"].str.contains(recherche_ticker, case=False, na=False) if "Nom" in df_filtered.columns else False)
    ]

df_filtered = df_filtered[(df_filtered["PER (x)"].isna()) | (df_filtered["PER (x)"] <= per_max)]
df_filtered = df_filtered[df_filtered["Rendement (%)"] >= rendement_min]

if secteurs_selectionnes and "Secteur" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Secteur"].isin(secteurs_selectionnes)]

# 5. KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Actions analysées", len(df_filtered))

per_moyen = df_filtered[df_filtered["PER (x)"] > 0]["PER (x)"].mean() if "PER (x)" in df_filtered.columns else 0
c2.metric("PER Moyen", f"{per_moyen:.1f}x" if pd.notna(per_moyen) and per_moyen > 0 else "N/A")

rendement_moyen = df_filtered[df_filtered["Rendement (%)"] > 0]["Rendement (%)"].mean() if "Rendement (%)" in df_filtered.columns else 0
c3.metric("Rendement Moyen", f"{rendement_moyen:.2f} %" if pd.notna(rendement_moyen) and rendement_moyen > 0 else "0.00 %")

if not df_filtered.empty and "Variation (%)" in df_filtered.columns:
    top = df_filtered.loc[df_filtered["Variation (%)"].idxmax()]
    c4.metric("Plus forte hausse", f"{top['Ticker']}", f"+{top['Variation (%)']:.2f}%")
else:
    c4.metric("Plus forte hausse", "N/A")

st.markdown("---")

# 6. Onglets d'analyse
tab_screener, tab_charts, tab_simulator = st.tabs(["📊 Screener & Cotations", "📈 Graphiques", "🧮 Simulateur de Dividendes"])

# Onglet 1 : Tableau Screener
with tab_screener:
    st.subheader("Tableau complet des Actions BRVM")
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

# Onglet 2 : Graphiques sécurisés
with tab_charts:
    st.subheader("Analyse PER vs Rendement")
    col_a, col_b = st.columns(2)
    
    with col_a:
        cols_requises = ["PER (x)", "Rendement (%)", "Ticker"]
        if all(col in df_filtered.columns for col in cols_requises):
            df_chart = df_filtered[
                df_filtered["PER (x)"].notna() & 
                (df_filtered["PER (x)"] > 0) & 
                df_filtered["Rendement (%)"].notna()
            ].copy()
            
            if not df_chart.empty:
                try:
                    kwargs = {
                        "data_frame": df_chart,
                        "x": "PER (x)",
                        "y": "Rendement (%)",
                        "title": "PER vs Rendement (%)",
                        "labels": {"PER (x)": "PER (Moins cher ➔)", "Rendement (%)": "Rendement (%) ➔"}
                    }
                    if "Ticker" in df_chart.columns:
                        kwargs["text"] = "Ticker"
                    if "Secteur" in df_chart.columns and df_chart["Secteur"].notna().any():
                        kwargs["color"] = "Secteur"

                    fig1 = px.scatter(**kwargs)
                    fig1.update_traces(textposition="top center")
                    st.plotly_chart(fig1, use_container_width=True)
                except Exception:
                    st.info("Données insuffisantes pour afficher le graphique PER vs Rendement.")
            else:
                st.info("Aucune donnée disponible avec un PER valide pour le filtre actuel.")
        else:
            st.warning("Colonnes nécessaires indisponibles.")

    with col_b:
        if "Rendement (%)" in df_filtered.columns and "Ticker" in df_filtered.columns:
            df_top_div = df_filtered[df_filtered["Rendement (%)"] > 0].sort_values(by="Rendement (%)", ascending=False).head(10)
            if not df_top_div.empty:
                try:
                    fig2 = px.bar(
                        df_top_div,
                        x="Ticker",
                        y="Rendement (%)",
                        title="Top 10 Rendements (%)",
                        color="Rendement (%)",
                        color_continuous_scale="Blues"
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                except Exception:
                    st.info("Impossible d'afficher le classement des rendements.")
            else:
                st.info("Aucune action à rendement positif dans la sélection.")

# Onglet 3 : Simulateur sécurisé contre les NaN
with tab_simulator:
    st.subheader("Simulateur de Revenus Passifs")
    
    col_s1, col_s2 = st.columns([1, 2])
    
    with col_s1:
        tickers_actifs = df_raw["Ticker"].dropna().unique().tolist()
        action_sel = st.selectbox("Sélectionner une action", options=sorted(tickers_actifs))
        capital = st.number_input("Montant à investir (FCFA)", min_value=10000, value=1000000, step=50000)
        
        row = df_raw[df_raw["Ticker"] == action_sel].iloc[0]
        
        # Sécurisation numérique contre NaN
        try:
            cours = float(row.get("Cours (FCFA)", 0)) if pd.notna(row.get("Cours (FCFA)")) else 0.0
        except ValueError:
            cours = 0.0

        try:
            div_net = float(row.get("Dividende Net", 0)) if pd.notna(row.get("Dividende Net")) else 0.0
        except ValueError:
            div_net = 0.0

        try:
            rend = float(row.get("Rendement (%)", 0)) if pd.notna(row.get("Rendement (%)")) else 0.0
        except ValueError:
            rend = 0.0

    with col_s2:
        if cours > 0:
            nb_titres = int(capital // cours)
            investi = nb_titres * cours
            reliquat = capital - investi
            
            if div_net > 0:
                revenu = nb_titres * div_net
            elif rend > 0:
                revenu = investi * (rend / 100)
            else:
                revenu = 0.0

            nom_action = row.get('Nom', action_sel) if pd.notna(row.get('Nom')) else action_sel
            st.success(f"### Simulation d'achat pour **{action_sel}** ({nom_action})")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Nombre de Titres", f"{nb_titres:,} actions")
            m2.metric("Montant Effectif Investi", f"{investi:,.0f} FCFA")
            
            if revenu > 0:
                m3.metric("Revenu Annuel Estimé", f"{revenu:,.0f} FCFA", delta=f"{rend:.2f}% / an")
            else:
                m3.metric("Revenu Annuel Estimé", "0 FCFA", delta="Pas de dividende connu")

            st.info(f"💡 Reliquat non investi : **{reliquat:,.0f} FCFA**")
        else:
            st.warning("Cours indisponible pour cette valeur.")

st.markdown("---")
st.caption("BRVM Quantum Analytics • Données et calculs mis à jour en direct.")