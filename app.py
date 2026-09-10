import io
import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="BRVM Quantum Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Optimisation : Cache fixé à 1 heure (3600 secondes) au lieu de 5 secondes
@st.cache_data(ttl=3600)
def get_data():
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
        from scraper import scraper_brvm_live
        scraper_brvm_live()
        conn = sqlite3.connect("brvm.db")
        df = pd.read_sql("SELECT * FROM screening", conn)
        conn.close()

    numeric_cols = [
        "Cours (FCFA)", "Variation (%)", "Capitalisation (FCFA)",
        "PER (x)", "P/B (x)", "Rendement (%)", "Dividende Net"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df

def get_historique_ticker(ticker):
    """Lecture de l'historique des cours d'une action."""
    db_paths = ["data/brvm.db", "brvm.db"]
    for path in db_paths:
        if os.path.exists(path):
            try:
                conn = sqlite3.connect(path)
                df_h = pd.read_sql(
                    "SELECT date, cours, variation FROM historique WHERE ticker = ? ORDER BY date ASC",
                    conn,
                    params=[ticker]
                )
                conn.close()
                return df_h
            except Exception:
                pass
    return pd.DataFrame()

df_raw = get_data()

st.title("📈 BRVM Quantum Analytics")
st.caption("Plateforme d'Analyse Financière & Screening Fondamental BRVM")

st.sidebar.header("⚙️ Configuration & Sync")

if st.sidebar.button("🔄 Actualiser les données"):
    from scraper import scraper_brvm_live
    scraper_brvm_live()
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtres & Screening")

recherche = st.sidebar.text_input("Recherche (Ticker / Nom)", "").upper()

secteurs_dispo = ["Tous"] + sorted(df_raw["Secteur"].dropna().unique().tolist())
secteur_sel = st.sidebar.selectbox("Secteur d'activité", options=secteurs_dispo)

# Filtres financiers intelligents
st.sidebar.subheader("🎯 Screening Fondamental")
per_max = st.sidebar.slider("PER Maximum (x)", min_value=1.0, max_value=40.0, value=40.0, step=0.5)
rendement_min = st.sidebar.slider("Rendement Minimum (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.5)
pb_max = st.sidebar.slider("P/B Maximum (x)", min_value=0.1, max_value=10.0, value=10.0, step=0.1)

# Application des filtres combinés
df_filtered = df_raw.copy()

if secteur_sel != "Tous":
    df_filtered = df_filtered[df_filtered["Secteur"] == secteur_sel]

if recherche:
    df_filtered = df_filtered[
        df_filtered["Ticker"].astype(str).str.contains(recherche, na=False) |
        df_filtered["Nom"].astype(str).str.contains(recherche, case=False, na=False)
    ]

if per_max < 40.0:
    df_filtered = df_filtered[(df_filtered["PER (x)"] <= per_max) & (df_filtered["PER (x)"] > 0)]

if rendement_min > 0.0:
    df_filtered = df_filtered[df_filtered["Rendement (%)"] >= rendement_min]

if pb_max < 10.0:
    df_filtered = df_filtered[(df_filtered["P/B (x)"] <= pb_max) & (df_filtered["P/B (x)"] > 0)]

# Métriques globales
c1, c2, c3, c4 = st.columns(4)
c1.metric("Actions sélectionnées", f"{len(df_filtered)} / {len(df_raw)}")

total_cap = df_filtered["Capitalisation (FCFA)"].sum()
c2.metric("Capitalisation Sélection", f"{total_cap / 1e9:.2f} Mds FCFA")

df_div_pos = df_filtered[df_filtered["Rendement (%)"] > 0]
r_moy = df_div_pos["Rendement (%)"].mean() if not df_div_pos.empty else 0.0
per_moy = df_filtered[df_filtered["PER (x)"] > 0]["PER (x)"].mean() if not df_filtered.empty else 0.0

c3.metric("PER Moyen", f"{per_moy:.1f} x")
c4.metric("Rendement Moyen", f"{r_moy:.2f} %")

tab1, tab2, tab3 = st.tabs(["📊 Screener BRVM", "📈 Top Rendements", "🧮 Simulateur & Historique"])

with tab1:
    col_exp1, col_exp2, _ = st.columns([1, 1, 3])
    
    csv_bytes = df_filtered.to_csv(index=False).encode('utf-8')
    col_exp1.download_button(
        label="📥 Exporter en CSV",
        data=csv_bytes,
        file_name="screener_brvm.csv",
        mime="text/csv"
    )

    buffer_excel = io.BytesIO()
    with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
        df_filtered.to_excel(writer, index=False, sheet_name='Screener')
    
    col_exp2.download_button(
        label="📊 Exporter en Excel",
        data=buffer_excel.getvalue(),
        file_name="screener_brvm.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.dataframe(
        df_filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cours (FCFA)": st.column_config.NumberColumn(format="%d FCFA"),
            "Variation (%)": st.column_config.NumberColumn(format="%.2f %%"),
            "Capitalisation (FCFA)": st.column_config.NumberColumn(format="%d FCFA"),
            "PER (x)": st.column_config.NumberColumn(format="%.1f x"),
            "P/B (x)": st.column_config.NumberColumn(format="%.2f x"),
            "Rendement (%)": st.column_config.NumberColumn(format="%.2f %%"),
            "Dividende Net": st.column_config.NumberColumn(format="%.2f FCFA"),
        }
    )

with tab2:
    if not df_filtered.empty:
        top_div = df_filtered[df_filtered["Rendement (%)"] > 0].sort_values(by="Rendement (%)", ascending=False).head(10)
        if not top_div.empty:
            fig = px.bar(
                top_div,
                x="Ticker",
                y="Rendement (%)",
                text="Rendement (%)",
                title="Top Rendements de la Sélection (%)",
                color="Rendement (%)",
                color_continuous_scale="Blues"
            )
            fig.update_traces(texttemplate='%{text:.2f}%', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

with tab3:
    tickers = df_raw["Ticker"].dropna().unique().tolist()
    if tickers:
        col1, col2 = st.columns(2)
        with col1:
            sel = st.selectbox("Action :", options=sorted(tickers))
        with col2:
            cap = st.number_input("Capital à investir (FCFA) :", value=1000000, step=100000)

        match = df_raw[df_raw["Ticker"] == sel]
        if not match.empty:
            row = match.iloc[0]
            c = float(row.get("Cours (FCFA)", 0))
            d = float(row.get("Dividende Net", 0))

            if c > 0:
                qty = int(cap // c)
                rev = qty * d
                st.success(f"""
                **Simulation pour {sel} :**
                * Actions achetées : **{qty:,}**
                * Prix unitaire : **{c:,.0f} FCFA**
                * Dividende annuel estimé : **{rev:,.0f} FCFA / an**
                """)
        
        # Courbe d'évolution temporelle
        st.markdown("---")
        st.subheader(f"📈 Historique du cours pour {sel}")
        df_h = get_historique_ticker(sel)
        if not df_h.empty and len(df_h) > 1:
            fig_hist = px.line(
                df_h, x="date", y="cours",
                title=f"Évolution temporelle du cours de {sel} (FCFA)",
                markers=True,
                labels={"date": "Date", "cours": "Prix (FCFA)"}
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("L'historique se construira progressivement à chaque mise à jour quotidienne.")