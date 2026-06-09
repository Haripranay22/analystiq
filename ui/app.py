"""
Phase 4 — Streamlit UI (Polished, Deployment-Ready)

Calls the LangGraph agent directly — no FastAPI hop needed.
Works locally (reads .env) and on Streamlit Community Cloud (reads st.secrets).

Run locally:  streamlit run ui/app.py
Deploy:       push to GitHub → connect on share.streamlit.io
"""

import json
import os
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Env setup: works locally (.env) AND on Streamlit Cloud (st.secrets) ───────
# Streamlit secrets don't auto-populate os.environ, so we do it manually.
# Agent nodes.py uses os.getenv() — this keeps it unchanged in both environments.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

for key in ["OPENAI_API_KEY", "DATABASE_URL", "OPENAI_MODEL"]:
    if key not in os.environ and hasattr(st, "secrets") and key in st.secrets:
        os.environ[key] = st.secrets[key]

# Add project root to path so `agent` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph import graph  # noqa: E402  (import after path setup)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AnalystIQ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Hide default Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Branded top bar */
.brand-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 0 8px 0;
    border-bottom: 1px solid #2A2D3E;
    margin-bottom: 24px;
}
.brand-title {
    font-size: 28px;
    font-weight: 700;
    color: #4F8EF7;
    margin: 0;
}
.brand-tag {
    font-size: 13px;
    color: #8B8FA8;
    margin: 0;
}

/* Metric cards */
.metric-row {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
}
.metric-card {
    background: #1A1D27;
    border: 1px solid #2A2D3E;
    border-radius: 10px;
    padding: 16px 20px;
    flex: 1;
}
.metric-label {
    font-size: 12px;
    color: #8B8FA8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 26px;
    font-weight: 700;
    color: #FAFAFA;
}
.metric-sub {
    font-size: 12px;
    color: #4F8EF7;
    margin-top: 2px;
}

/* Result card */
.result-card {
    background: #1A1D27;
    border: 1px solid #2A2D3E;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.insight-text {
    font-size: 15px;
    line-height: 1.7;
    color: #D0D3E8;
}

/* Ask button */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #4F8EF7;
    border: none;
    padding: 10px 32px;
    font-size: 15px;
    font-weight: 600;
    border-radius: 8px;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #3A7AE4;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="brand-bar">
    <div>
        <p class="brand-title">📊 AnalystIQ</p>
        <p class="brand-tag">AI Copilot for Data Analysts &nbsp;·&nbsp; Ask in English, get SQL + insights</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Live DB metrics row ────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_db_metrics():
    """Pull headline numbers from the DB once, cache for 5 min."""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(os.getenv("DATABASE_URL", ""))
        with engine.connect() as conn:
            customers  = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            txns       = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
            fraud_rate = conn.execute(text(
                "SELECT ROUND(100.0 * SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) / COUNT(*), 1) FROM transactions"
            )).scalar()
            avg_credit = conn.execute(text("SELECT ROUND(AVG(credit_score)) FROM customers")).scalar()
        return {"customers": customers, "txns": txns, "fraud_rate": fraud_rate, "avg_credit": avg_credit}
    except Exception:
        return None

metrics = load_db_metrics()

if metrics:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Customers</div>
            <div class="metric-value">{metrics['customers']:,}</div>
            <div class="metric-sub">across all segments</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Transactions</div>
            <div class="metric-value">{metrics['txns']:,}</div>
            <div class="metric-sub">last 12 months</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Fraud Rate</div>
            <div class="metric-value">{metrics['fraud_rate']}%</div>
            <div class="metric-sub">of all transactions</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Credit Score</div>
            <div class="metric-value">{metrics['avg_credit']}</div>
            <div class="metric-sub">FICO-style, 300–850</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Try these questions")
    examples = [
        "How many customers do we have by segment?",
        "What are the top 5 merchants by total transaction amount?",
        "Show total transactions per month in the last year",
        "How many customers have a credit score above 700?",
        "What is the fraud rate by transaction category?",
        "Which account types have the highest average balance?",
        "How many fraud flags were confirmed vs false positive?",
        "What is the average credit score by customer segment?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["q"] = ex

    st.divider()
    st.markdown("""
    <div style="font-size:12px; color:#8B8FA8; line-height:1.6">
    <b>Stack</b><br>
    GPT-4o-mini · LangGraph<br>
    FastAPI · PostgreSQL · Streamlit<br><br>
    <b>Built by</b><br>
    Haripranay Peddagolla<br>
    Senior Data Analyst
    </div>
    """, unsafe_allow_html=True)

# ── Question input ─────────────────────────────────────────────────────────────

col_input, col_btn = st.columns([5, 1])
with col_input:
    question = st.text_input(
        label="question",
        placeholder="e.g. What are the top 5 merchants by fraud amount?",
        key="q",
        label_visibility="collapsed",
    )
with col_btn:
    run = st.button("Ask", type="primary", use_container_width=True)

# ── Chart detection ────────────────────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#1A1D27",
    plot_bgcolor="#1A1D27",
    font_color="#FAFAFA",
    margin=dict(l=20, r=20, t=40, b=20),
    xaxis=dict(gridcolor="#2A2D3E"),
    yaxis=dict(gridcolor="#2A2D3E"),
)

def detect_and_render_chart(df: pd.DataFrame) -> bool:
    if df.empty or len(df.columns) < 2:
        return False

    cols           = list(df.columns)
    numeric_cols   = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    date_cols      = [c for c in cols if any(k in c.lower() for k in ["month", "date", "week", "year", "period"])]
    label_cols     = [c for c in cols if c not in numeric_cols]

    # Single row single number — handled upstream as metric
    if len(df) == 1 and len(numeric_cols) == 1:
        return False

    # Trend — line chart
    if date_cols and numeric_cols:
        x, y = date_cols[0], numeric_cols[0]
        color = label_cols[0] if len(label_cols) > 1 else None
        fig = px.line(df, x=x, y=y, color=color, markers=True,
                      title=f"{y.replace('_',' ').title()} over Time",
                      color_discrete_sequence=["#4F8EF7", "#F7874F", "#4FF7A0"])
        fig.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)
        return True

    # Ranking / comparison — horizontal bar
    if label_cols and numeric_cols:
        x, y = numeric_cols[0], label_cols[0]
        df_plot = df.sort_values(x, ascending=True).tail(20)
        fig = px.bar(df_plot, x=x, y=y, orientation="h",
                     title=f"{x.replace('_',' ').title()} by {y.replace('_',' ').title()}",
                     color=x, color_continuous_scale=["#1A3A6E", "#4F8EF7"])
        fig.update_layout(**PLOTLY_LAYOUT, showlegend=False,
                          coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
        return True

    return False

# ── Run agent ─────────────────────────────────────────────────────────────────

if run and question.strip():
    with st.spinner("Running agent..."):
        try:
            final_state = graph.invoke({
                "question": question,
                "schema": "", "sql": "", "result": "",
                "error": "", "explanation": "", "retry_count": 0,
            })
        except Exception as e:
            st.error(f"Agent error: {e}")
            st.stop()

    error      = final_state.get("error", "")
    result_str = final_state.get("result", "[]")
    sql        = final_state.get("sql", "")
    explanation= final_state.get("explanation", "")
    retries    = final_state.get("retry_count", 0)

    # Hard failure
    if error and not result_str:
        st.error(f"Query failed after {retries} retries: {error}")

    else:
        rows = json.loads(result_str or "[]")
        df   = pd.DataFrame(rows)

        # Single metric
        if len(df) == 1 and len(df.columns) == 1:
            val      = df.iloc[0, 0]
            label    = df.columns[0].replace("_", " ").title()
            fmt_val  = f"{int(val):,}" if isinstance(val, (int, float)) and float(val) == int(val) else val
            st.markdown(f"""
            <div class="result-card" style="text-align:center; padding: 32px;">
                <div class="metric-label">{label}</div>
                <div style="font-size:52px; font-weight:700; color:#4F8EF7; margin:8px 0">{fmt_val}</div>
            </div>""", unsafe_allow_html=True)

        else:
            chart_rendered = detect_and_render_chart(df)

            st.markdown("**Results**")
            st.dataframe(
                df, use_container_width=True, hide_index=True,
                height=min(400, 38 + len(df) * 35),
            )

        # Insight
        st.markdown(f"""
        <div class="result-card">
            <div class="metric-label">Insight</div>
            <div class="insight-text">{explanation}</div>
        </div>""", unsafe_allow_html=True)

        # SQL expander
        with st.expander("View generated SQL", expanded=False):
            st.code(sql, language="sql")
            if retries > 0:
                st.caption(f"Self-corrected {retries} time(s) before succeeding.")

elif run and not question.strip():
    st.warning("Enter a question first.")
