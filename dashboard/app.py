import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Blockchain Incident Dashboard",
                   layout="wide", page_icon="🔐")


@st.cache_data
def load_data():
    df = pd.read_csv("data/master.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["source_file"] != "master"]  # ← ADD THIS
    return df


df = load_data()

# ── HEADER ──────────────────────────────────────────────
st.title("🔐 Blockchain Security Incident Tracker")


# ── KPI CARDS ───────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("🗂️ Total Incidents", f"{len(df):,}")
col2.metric("⛓️ Blockchains Tracked", "20")
col3.metric("📅 Years Covered",
            f"{df['date'].min().year} – {df['date'].max().year}")
col4.metric("⚠️ Needs Manual Review",
            df["type_of_malicious_activity"].str.contains("review", na=True).sum())

st.divider()

# ── ROW 1: Incidents per Blockchain ─────────────────────
st.subheader("📦 Incidents per Blockchain")
bc_counts = (df.groupby("source_file")
               .size()
               .reset_index(name="count")
               .sort_values("count", ascending=False))
bc_counts = bc_counts[bc_counts["source_file"] != "master"]
fig1 = px.bar(bc_counts, x="source_file", y="count",
              color="count", color_continuous_scale="Blues",
              text="count", labels={"source_file": "Blockchain", "count": "Incidents"})
fig1.update_traces(textposition="outside")
fig1.update_layout(showlegend=False)
st.plotly_chart(fig1, use_container_width=True)

st.divider()

# ── ROW 2: Attack type + Timeline ───────────────────────
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🎯 Attack Type Distribution")
    atk = (df["type_of_malicious_activity"]
           .fillna("Unknown")
           .value_counts()
           .reset_index())
    atk.columns = ["Attack Type", "Count"]
    fig2 = px.pie(atk, names="Attack Type", values="Count", hole=0.4)
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig2, use_container_width=True)

with col_b:
    st.subheader("📅 Incidents Over Time (Monthly)")
    timeline = (df.dropna(subset=["date"])
                  .groupby(df["date"].dt.to_period("M"))
                  .size()
                  .reset_index(name="count"))
    timeline["date"] = timeline["date"].astype(str)
    fig3 = px.line(timeline, x="date", y="count", markers=True,
                   labels={"date": "Month", "count": "Incidents"})
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── ROW 3: Theme tags + Tech ────────────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.subheader("🏷️ Top Theme Tags")
    tags = (df["theme_tags"].dropna()
            .str.split(", ").explode()
            .value_counts().head(10)
            .reset_index())
    tags.columns = ["Tag", "Count"]
    fig4 = px.bar(tags, x="Count", y="Tag", orientation="h",
                  color="Count", color_continuous_scale="Teal")
    fig4.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

with col_d:
    st.subheader("⚙️ Tech Stack Involved")
    tech = (df["tech"].dropna()
            .str.split(", ").explode()
            .value_counts().head(10)
            .reset_index())
    tech.columns = ["Tech", "Count"]
    fig5 = px.bar(tech, x="Count", y="Tech", orientation="h",
                  color="Count", color_continuous_scale="Oranges")
    fig5.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig5, use_container_width=True)

st.divider()

# ── FILTER + TABLE ──────────────────────────────────────
st.subheader("🔍 Browse Incidents")
col_f1, col_f2 = st.columns(2)

with col_f1:
    chains = ["All"] + sorted(df["source_file"].dropna().unique().tolist())
    selected_chain = st.selectbox("Filter by Blockchain", chains)

with col_f2:
    attack_types = [
        "All"] + sorted(df["type_of_malicious_activity"].dropna().unique().tolist())
    selected_attack = st.selectbox("Filter by Attack Type", attack_types)

filtered = df.copy()
if selected_chain != "All":
    filtered = filtered[filtered["source_file"] == selected_chain]
if selected_attack != "All":
    filtered = filtered[filtered["type_of_malicious_activity"]
                        == selected_attack]

st.dataframe(
    filtered[["date", "title", "source_file",
              "type_of_malicious_activity", "theme_tags"]]
    .rename(columns={"source_file": "blockchain",
                     "type_of_malicious_activity": "attack_type"})
    .sort_values("date", ascending=False),
    use_container_width=True
)

st.caption(f"Showing {len(filtered):,} of {len(df):,} incidents")
