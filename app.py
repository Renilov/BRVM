import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

# 1. Configuration de la page
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


# 2. Chargement sécurisé avec recalcul dynamique du rendement
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

    # Si la base est introuvable, exécuter le scraper directement
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
        st.error("Impossible de charger les données BRVM.")
        return pd.DataFrame()

    # Nettoyage strict des données numériques
    for col in ["Cours (FCFA)", "Variation (%)", "PER (x)", "Rendement (%)", "Dividende Net"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Recalcul dynamique garanti du Rendement (%) = (Dividende Net / Cours) * 100
    df["Rendement (%)"] = df.apply(
        lambda r: round((r["Dividende Net"] / r["Cours (FCFA)"]) * 100, 2)
        if (pd.notna(r["Dividende Net"]) and pd.notna(r["Cours (FCFA)"]) and r["Cours (FCFA)"] > 0 and r["Dividende Net"] > 0)
        else 0.0,
        axis=1
    )

    return df


# 3. Chargement des données
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

# Filtrage
df_filtered = df_raw.copy()

if recherche_ticker:
    df_filtered = df_filtered[
        df_filtered["Ticker"].str.contains(recherche_ticker, na=False) |
        df_filtered["Nom"].str.contains(recherche_ticker, case=False, na=False)
    ]

df_filtered = df_filtered[(df_filtered["PER (x)"].isna()) | (df_filtered["PER (x)"] <= per_max)]
df_filtered = df_filtered[df_filtered["Rendement (%)"] >= rendement_min]

if secteurs_selectionnes:
    df_filtered = df_filtered[df_filtered["Secteur"].isin(secteurs_selectionnes)]

# 5. KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Actions analysées", len(df_filtered))

per_moyen = df_filtered[df_filtered["PER (x)"] > 0]["PER (x)"].mean()
c2.metric("PER Moyen", f"{per_moyen:.1f}x" if pd.notna(per_moyen) else "N/A")

rendement_moyen = df_filtered[df_filtered["Rendement (%)"] > 0]["Rendement (%)"].mean()
c3.metric("Rendement Moyen", f"{rendement_moyen:.2f} %" if pd.notna(rendement_moyen) else "0.00 %")

if not df_filtered.empty and "Variation (%)" in df_filtered.columns:
    top = df_filtered.loc[df_filtered["Variation (%)"].idxmax()]
    c4.metric("Plus forte hausse", f"{top['Ticker']}", f"+{top['Variation (%)']:.2f}%")
else:
    c4.metric("Plus forte hausse", "N/A")

st.markdown("---")

# 6. Onglets
tab_screener, tab_charts, tab_simulator = st.tabs(["📊 Screener & Cotations", "📈 Graphiques", "🧮 Simulateur de Dividendes"])

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

with tab_charts:
    st.subheader("Analyse PER vs Rendement")
    col_a, col_b = st.columns(2)
    
    with col_a:
        df_chart = df_filtered[df_filtered["PER (x)"].notna() & (df_filtered["PER (x)"] > 0)]
        if not df_chart.empty:
            fig1 = px.scatter(
                df_chart,
                x="PER (x)",
                y="Rendement (%)",
                text="Ticker",
                color="Secteur",
                title="PER vs Rendement (%)",
                labels={"PER (x)": "PER (Moins cher ➔)", "Rendement (%)": "Rendement (%) ➔"}
            )
            fig1.update_traces(textposition="top center")
            st.plotly_chart(fig1, use_container_width=True)
            
    with col_b:
        df_top_div = df_filtered.sort_values(by="Rendement (%)", ascending=False).head(10)
        if not df_top_div.empty:
            fig2 = px.bar(
                df_top_div,
                x="Ticker",
                y="Rendement (%)",
                title="Top 10 Rendements (%)",
                color="Rendement (%)",
                color_continuous_scale="Blues"
            )
            st.plotly_chart(fig2, use_container_width=True)

with tab_simulator:
    st.subheader("Simulateur de Revenus Passifs")
    
    col_s1, col_s2 = st.columns([1, 2])
    
    with col_s1:
        tickers_actifs = df_raw["Ticker"].dropna().unique().tolist()
        action_sel = st.selectbox("Sélectionner une action", options=sorted(tickers_actifs))
        capital = st.number_input("Montant à investir (FCFA)", min_value=10000, value=1000000, step=50000)
        
        row = df_raw[df_raw["Ticker"] == action_sel].iloc[0]
        cours = float(row.get("Cours (FCFA)", 0) or 0)
        div_net = float(row.get("Dividende Net", 0) or 0)
        rend = float(row.get("Rendement (%)", 0) or 0)

    with col_s2:
        if cours > 0:
            nb_titres = int(capital // cours)
            investi = nb_titres * cours
            reliquat = capital - investi
            revenu = nb_titres * div_net

            st.success(f"### Simulation d'achat pour **{action_sel}** ({row['Nom']})")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Nombre de Titres", f"{nb_titres:,} actions")
            m2.metric("Montant Effectif Investi", f"{investi:,.0f} FCFA")
            
            if div_net > 0:
                m3.metric("Revenu Annuel Estimé", f"{revenu:,.0f} FCFA", delta=f"{rend:.2f}% / an")
            else:
                m3.metric("Revenu Annuel Estimé", "0 FCFA", delta="Pas de dividende")

            st.info(f"💡 Reliquat non investi : **{reliquat:,.0f} FCFA**")
        else:
            st.warning("Cours indisponible pour cette valeur.")

st.markdown("---")
st.caption("BRVM Quantum Analytics • Cotations et calculs mis à jour en direct.")