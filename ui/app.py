"""
Phase 4 — Streamlit UI

The analyst-facing front end. No JSON, no Swagger — just a clean interface where
an analyst types a plain English question and gets back SQL, results, and a chart.

Run with: streamlit run ui/app.py
"""

import json

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AnalystIQ",
    page_icon="📊",
    layout="wide",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📊 AnalystIQ")
st.caption("Ask plain English questions about your fintech data. Get back SQL, results, and charts.")

# ── Sidebar — example questions ───────────────────────────────────────────────

with st.sidebar:
    st.header("Example Questions")
    st.markdown("Click any question to load it:")

    examples = [
        "How many customers do we have by segment?",
        "What are the top 5 merchants by total transaction amount?",
        "Show me total transactions per month in the last year",
        "How many customers have a credit score above 700?",
        "What is the fraud rate by transaction category?",
        "Which account types have the highest average balance?",
        "How many fraud flags were confirmed vs false positive?",
        "What is the average credit score by customer segment?",
    ]

    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state["question_input"] = example

    st.divider()
    st.caption("Powered by GPT-4o-mini + LangGraph")

# ── Question input ─────────────────────────────────────────────────────────────

question = st.text_input(
    label="Your question",
    placeholder="e.g. What are the top 5 merchants by total transaction amount?",
    key="question_input",
    label_visibility="collapsed",
)

run = st.button("Ask", type="primary", use_container_width=False)

# ── Auto-chart detection ───────────────────────────────────────────────────────

def detect_and_render_chart(df: pd.DataFrame, question: str) -> bool:
    """
    Tries to pick the right chart type from the shape of the result.
    Returns True if a chart was rendered, False if table-only is appropriate.

    Rules:
    - 1 row, 1 col  → single metric (big number, no chart)
    - date/month col + numeric col → line chart (trend over time)
    - label col + 1 numeric col → bar chart (comparison / ranking)
    - everything else → table only
    """
    if df.empty or len(df.columns) < 2:
        return False

    cols = list(df.columns)

    # Identify column types
    date_cols = [c for c in cols if any(kw in c.lower() for kw in ["month", "date", "week", "year", "period"])]
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    label_cols = [c for c in cols if c not in numeric_cols]

    # Single row single number — render as metric instead
    if len(df) == 1 and len(numeric_cols) == 1 and len(cols) <= 2:
        return False

    # Trend over time — line chart
    if date_cols and numeric_cols:
        x = date_cols[0]
        y = numeric_cols[0]
        color = label_cols[0] if len(label_cols) > 1 else None
        fig = px.line(
            df, x=x, y=y, color=color,
            title=f"{y.replace('_', ' ').title()} over {x.replace('_', ' ').title()}",
            markers=True,
        )
        fig.update_layout(xaxis_title=x.replace("_", " ").title(), yaxis_title=y.replace("_", " ").title())
        st.plotly_chart(fig, use_container_width=True)
        return True

    # Ranking / comparison — horizontal bar chart (easier to read labels)
    if label_cols and numeric_cols:
        x = numeric_cols[0]
        y = label_cols[0]
        color = numeric_cols[1] if len(numeric_cols) > 1 else None
        # Sort for a clean ranked view
        df_sorted = df.sort_values(x, ascending=True).tail(20)  # cap at 20 bars
        fig = px.bar(
            df_sorted, x=x, y=y, orientation="h", color=color,
            title=f"{x.replace('_', ' ').title()} by {y.replace('_', ' ').title()}",
            color_continuous_scale="Blues" if color else None,
        )
        fig.update_layout(yaxis_title="", xaxis_title=x.replace("_", " ").title())
        st.plotly_chart(fig, use_container_width=True)
        return True

    return False


# ── Main response area ─────────────────────────────────────────────────────────

if run and question.strip():
    with st.spinner("Running agent..."):
        try:
            resp = requests.post(
                f"{API_URL}/query",
                json={"question": question},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API. Make sure `uvicorn api.main:app --reload` is running.")
            st.stop()
        except Exception as e:
            st.error(f"Request failed: {e}")
            st.stop()

    # ── Result ────────────────────────────────────────────────────────────────

    if data.get("error") and not data.get("result"):
        st.error(f"Agent failed after {data['retry_count']} retries.\n\n**Error:** {data['error']}")
    else:
        rows = json.loads(data.get("result", "[]"))
        df = pd.DataFrame(rows)

        # Single metric — show big number
        if len(df) == 1 and len(df.columns) == 1:
            val = df.iloc[0, 0]
            col_name = df.columns[0].replace("_", " ").title()
            st.metric(label=col_name, value=f"{val:,}" if isinstance(val, (int, float)) else val)

        else:
            # Try to render a chart; always show table below it
            chart_rendered = detect_and_render_chart(df, question)

            # Results table
            st.subheader("Results")
            st.dataframe(df, use_container_width=True, hide_index=True)

            if not chart_rendered:
                st.caption("No chart rendered — result shape doesn't map to a clear visualization.")

        # ── Explanation ───────────────────────────────────────────────────────
        st.subheader("Insight")
        st.write(data.get("explanation", ""))

        # ── SQL — collapsible ─────────────────────────────────────────────────
        with st.expander("View SQL", expanded=False):
            st.code(data.get("sql", ""), language="sql")
            if data.get("retry_count", 0) > 0:
                st.caption(f"Self-corrected {data['retry_count']} time(s) before succeeding.")

elif run and not question.strip():
    st.warning("Please enter a question first.")
