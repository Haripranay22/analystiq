"""
ui/app.py — AnalystIQ Production UI

Chat-based interface for querying the fintech database in plain English.
Calls the FastAPI backend via ui/api_client.py — no direct agent imports.
Chat history is persisted to Postgres via ui/db.py — refresh-safe.
"""

import io
import json
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Page config MUST be the first Streamlit call — before st.secrets ──────────
st.set_page_config(
    page_title="AnalystIQ",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Env: local (.env) and Streamlit Cloud (st.secrets) ───────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    _secrets = dict(st.secrets)
    for _key in ["OPENAI_API_KEY", "DATABASE_URL", "OPENAI_MODEL", "API_URL"]:
        if _key not in os.environ and _key in _secrets:
            os.environ[_key] = _secrets[_key]
except Exception:
    pass  # No secrets.toml locally — .env handles it

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import api_client, db  # noqa: E402

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }

.brand { font-size:22px; font-weight:700; color:#4F8EF7; margin:0 0 2px 0; }
.brand-sub { font-size:12px; color:#8B8FA8; margin:0 0 16px 0; }

.schema-type { font-size:11px; color:#8B8FA8; font-family:monospace; }
.schema-pk   { font-size:10px; color:#4F8EF7; font-weight:600; }

.meta-strip  { font-size:12px; color:#8B8FA8; margin: 4px 0 8px 0; }
.meta-ok     { color:#4ADE80; }
.meta-err    { color:#F87171; }

.suggestion-hint { font-size:12px; color:#8B8FA8; margin:8px 0 4px 0; }

div[data-testid="stChatMessage"] { padding: 8px 0; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ─────────────────────────────────────────────────────

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []   # list of dicts from db.get_messages()
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Helpers ───────────────────────────────────────────────────────────────────

CHART_TYPES = ["Auto", "Bar", "Line", "Area", "Pie", "Scatter"]

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#0F1117", plot_bgcolor="#0F1117", font_color="#FAFAFA",
    margin=dict(l=20, r=20, t=36, b=20),
    xaxis=dict(gridcolor="#2A2D3E"), yaxis=dict(gridcolor="#2A2D3E"),
)


def _df_from_json(result_json: str) -> pd.DataFrame:
    try:
        return pd.DataFrame(json.loads(result_json or "[]"))
    except Exception:
        return pd.DataFrame()


def _auto_chart(df: pd.DataFrame, override: str = "Auto"):
    """Return a Plotly figure or None if no sensible chart exists."""
    if df.empty or len(df.columns) < 2:
        return None
    cols         = list(df.columns)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    date_cols    = [c for c in cols if any(k in c.lower() for k in ["month","date","week","year","period"])]
    label_cols   = [c for c in cols if c not in numeric_cols]

    if not numeric_cols:
        return None

    x_num = numeric_cols[0]
    x_lbl = label_cols[0] if label_cols else cols[0]

    chart = override if override != "Auto" else (
        "Line" if date_cols else "Bar"
    )

    try:
        if chart == "Bar":
            df_plot = df.sort_values(x_num, ascending=True).tail(20)
            fig = px.bar(df_plot, x=x_num, y=x_lbl, orientation="h",
                         color=x_num, color_continuous_scale=["#1A3A6E","#4F8EF7"])
            fig.update_layout(**PLOTLY_LAYOUT, coloraxis_showscale=False)
        elif chart == "Line":
            x_axis = date_cols[0] if date_cols else cols[0]
            fig = px.line(df, x=x_axis, y=x_num, markers=True,
                          color_discrete_sequence=["#4F8EF7"])
            fig.update_layout(**PLOTLY_LAYOUT)
        elif chart == "Area":
            x_axis = date_cols[0] if date_cols else cols[0]
            fig = px.area(df, x=x_axis, y=x_num,
                          color_discrete_sequence=["#4F8EF7"])
            fig.update_layout(**PLOTLY_LAYOUT)
        elif chart == "Pie":
            fig = px.pie(df, names=x_lbl, values=x_num,
                         color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_layout(**PLOTLY_LAYOUT)
        elif chart == "Scatter":
            y_col = numeric_cols[1] if len(numeric_cols) > 1 else x_num
            fig = px.scatter(df, x=x_num, y=y_col,
                             color_discrete_sequence=["#4F8EF7"])
            fig.update_layout(**PLOTLY_LAYOUT)
        else:
            return None
        return fig
    except Exception:
        return None


def _render_answer_card(msg: dict, card_key: str):
    """Render a single assistant message as tabbed answer card."""
    df         = _df_from_json(msg.get("result_json") or "[]")
    sql        = msg.get("sql") or ""
    expl       = msg.get("explanation") or ""
    elapsed    = msg.get("elapsed_ms") or 0
    error      = msg.get("error") or ""
    row_count  = len(df)

    if error and not msg.get("result_json"):
        st.error(f"Query failed: {error}")
        return

    # Metadata strip
    status_icon = "✓" if not error else "⚠"
    status_cls  = "meta-ok" if not error else "meta-err"
    st.markdown(
        f'<div class="meta-strip">'
        f'<span class="{status_cls}">{status_icon} {row_count} rows</span>'
        f' · {elapsed:,}ms'
        f'</div>',
        unsafe_allow_html=True,
    )

    tab_results, tab_sql, tab_chart, tab_expl = st.tabs(
        ["📋 Results", "🔍 SQL", "📊 Chart", "💡 Explanation"]
    )

    # ── Results tab ───────────────────────────────────────────────────────────
    with tab_results:
        if df.empty:
            st.info("No rows returned.")
        elif len(df) == 1 and len(df.columns) == 1:
            val   = df.iloc[0, 0]
            label = df.columns[0].replace("_", " ").title()
            fmt   = f"{int(val):,}" if isinstance(val, (int, float)) and float(val) == int(float(val)) else str(val)
            st.metric(label=label, value=fmt)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True,
                         height=min(400, 38 + row_count * 35))

            col_csv, col_xl, _ = st.columns([1, 1, 6])
            with col_csv:
                st.download_button(
                    "⬇ CSV", df.to_csv(index=False).encode(),
                    file_name="analystiq_result.csv", mime="text/csv",
                    key=f"csv_{card_key}",
                )
            with col_xl:
                buf = io.BytesIO()
                df.to_excel(buf, index=False, engine="openpyxl")
                st.download_button(
                    "⬇ Excel", buf.getvalue(),
                    file_name="analystiq_result.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"xl_{card_key}",
                )

    # ── SQL tab ───────────────────────────────────────────────────────────────
    with tab_sql:
        st.code(sql, language="sql")

        if st.toggle("Edit & re-run", key=f"toggle_{card_key}"):
            edited = st.text_area("Edit SQL below:", value=sql,
                                  height=120, key=f"edit_{card_key}")
            if st.button("▶ Run edited SQL", key=f"run_{card_key}"):
                with st.spinner("Running…"):
                    try:
                        resp = api_client.execute_sql(edited)
                        if resp.get("error"):
                            st.error(resp["error"])
                        else:
                            df2 = _df_from_json(resp.get("result", "[]"))
                            st.success(f"{resp['row_count']} rows · {resp['elapsed_ms']}ms")
                            st.dataframe(df2, use_container_width=True, hide_index=True)
                    except api_client.APIError as e:
                        st.error(e.detail)

    # ── Chart tab ─────────────────────────────────────────────────────────────
    with tab_chart:
        if df.empty or len(df.columns) < 2:
            st.info("No chart available for single-value or empty results.")
        else:
            override = st.selectbox("Chart type", CHART_TYPES,
                                    key=f"chart_type_{card_key}")
            fig = _auto_chart(df, override)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Could not build a chart for this result shape.")

    # ── Explanation tab ───────────────────────────────────────────────────────
    with tab_expl:
        if expl:
            st.markdown(expl)
        else:
            st.info("No explanation available.")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<p class="brand">🔍 AnalystIQ</p>', unsafe_allow_html=True)
    st.markdown('<p class="brand-sub">AI Copilot for Data Analysts</p>', unsafe_allow_html=True)

    # New chat button
    if st.button("＋ New chat", use_container_width=True, type="primary"):
        tid = db.create_thread()
        st.session_state.thread_id = tid
        st.session_state.messages  = []
        st.rerun()

    st.divider()

    # Chat history
    threads = db.list_threads()
    if threads:
        st.markdown("**Recent chats**")
        for t in threads:
            is_active = t["id"] == st.session_state.thread_id
            label = ("▶ " if is_active else "") + t["title"]
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                if st.button(label, key=f"thread_{t['id']}", use_container_width=True):
                    st.session_state.thread_id = t["id"]
                    st.session_state.messages  = db.get_messages(t["id"])
                    st.rerun()
            with col_del:
                if st.button("✕", key=f"del_{t['id']}"):
                    db.delete_thread(t["id"])
                    if st.session_state.thread_id == t["id"]:
                        st.session_state.thread_id = None
                        st.session_state.messages  = []
                    st.rerun()

    st.divider()

    # Schema browser
    with st.expander("🗂 Schema browser", expanded=False):
        try:
            schema_data = api_client.get_schema()
            for tbl in schema_data.get("tables", []):
                st.markdown(f"**{tbl['name']}**")
                for col in tbl["columns"]:
                    pk_badge = ' <span class="schema-pk">PK</span>' if col.get("is_pk") else ""
                    st.markdown(
                        f'<div style="padding-left:12px">'
                        f'{col["name"]}'
                        f'<span class="schema-type"> {col["type"]}</span>'
                        f'{pk_badge}</div>',
                        unsafe_allow_html=True,
                    )
        except api_client.APIError as e:
            st.warning(f"Schema unavailable: {e.detail}")

    st.divider()
    st.markdown("""
    <div style="font-size:11px;color:#8B8FA8;line-height:1.7">
    GPT-4o-mini · LangGraph · FastAPI<br>
    PostgreSQL · Streamlit<br><br>
    Built by <b>Haripranay Peddagolla</b>
    </div>""", unsafe_allow_html=True)

# ── Main area — ensure we have an active thread ───────────────────────────────

if st.session_state.thread_id is None:
    # ── Empty state ───────────────────────────────────────────────────────────
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("## Welcome to AnalystIQ")
        st.markdown("Ask plain English questions about your fintech data. "
                    "Get back SQL, results, charts, and insights — instantly.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Try one of these:**")
        examples = [
            "How many customers do we have by segment?",
            "What are the top 5 merchants by total transaction amount?",
            "What is the fraud rate by transaction category?",
            "Show total transactions per month in the last year",
        ]
        for ex in examples:
            if st.button(ex, use_container_width=True, key=f"ex_{ex}"):
                tid = db.create_thread(title=ex[:60])
                st.session_state.thread_id = tid
                st.session_state.messages  = []
                st.session_state.pending_question = ex
                st.rerun()
else:
    # ── Active thread — render chat history ───────────────────────────────────
    if not st.session_state.messages:
        st.session_state.messages = db.get_messages(st.session_state.thread_id)

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["question"])
        else:
            with st.chat_message("assistant"):
                card_key = str(msg["id"])
                _render_answer_card(msg, card_key)

    # ── Process pending question (from example buttons or suggestions) ────────
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = None

        db.save_user_message(st.session_state.thread_id, question)

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.status("Thinking…", expanded=True) as status:
                status.write("Generating SQL…")
                try:
                    resp = api_client.query(question)
                    status.write("Running query…")
                    status.write("Building chart…")
                    status.update(label="Done", state="complete", expanded=False)

                    mid = db.save_assistant_message(
                        thread_id=st.session_state.thread_id,
                        question=question,
                        sql=resp.get("sql", ""),
                        result_json=resp.get("result", "[]"),
                        explanation=resp.get("explanation", ""),
                        elapsed_ms=resp.get("elapsed_ms", 0),
                        error=resp.get("error", ""),
                    )
                    msg_record = {
                        "id": mid, "role": "assistant",
                        "question": question,
                        "sql": resp.get("sql", ""),
                        "result_json": resp.get("result", "[]"),
                        "explanation": resp.get("explanation", ""),
                        "elapsed_ms": resp.get("elapsed_ms", 0),
                        "error": resp.get("error", ""),
                    }
                    st.session_state.messages.append(
                        {"role": "user", "question": question, "id": None}
                    )
                    st.session_state.messages.append(msg_record)
                    _render_answer_card(msg_record, str(mid))

                    # Auto-rename thread on first message
                    if len(st.session_state.messages) <= 2:
                        db.rename_thread(st.session_state.thread_id, question[:60])

                    # Follow-up suggestions
                    result_preview = resp.get("result", "[]")[:500]
                    suggestions = api_client.get_suggestions(
                        question, resp.get("sql", ""), result_preview
                    )
                    if suggestions:
                        st.markdown('<div class="suggestion-hint">Suggested follow-ups:</div>',
                                    unsafe_allow_html=True)
                        for i, sug in enumerate(suggestions):
                            if st.button(sug, key=f"sug_{mid}_{i}"):
                                st.session_state.pending_question = sug
                                st.rerun()

                except api_client.APIError as e:
                    status.update(label="Error", state="error", expanded=False)
                    st.error(f"**{e.status_code}** — {e.detail}")

        st.rerun()

# ── Chat input (pinned bottom) ────────────────────────────────────────────────

if st.session_state.thread_id is not None:
    if prompt := st.chat_input("Ask a question about your data…"):
        st.session_state.pending_question = prompt
        st.rerun()
