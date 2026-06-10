# AnalystIQ — AI Copilot for Data Analysts

> Ask a question in plain English. Get back SQL, results, charts, and a plain-English insight — instantly.

Built by **Haripranay Peddagolla** — Senior Data Analyst with 4+ years in fintech (State Street, KPIT Technologies). This project demonstrates what a modern analyst can build when SQL expertise meets AI engineering.

---

## The Problem It Solves

A data analyst at a fintech company spends hours writing ad-hoc SQL, explaining results to stakeholders, and re-running the same queries with slightly different filters. AnalystIQ collapses that loop to seconds:

| Without AnalystIQ | With AnalystIQ |
|---|---|
| Write SQL manually | Type a question in English |
| Debug syntax errors | Agent self-corrects up to 3 times |
| Copy-paste results to Excel | Download CSV or Excel in one click |
| Explain numbers in an email | Plain-English insight generated automatically |
| Guess at the right chart type | Chart auto-selected from result shape |

---

## Screenshots

### Welcome Screen — Live DB Metrics + Example Questions
![Welcome Screen](assets/01_welcome.png)

### Results Tab — Sortable Table with CSV/Excel Export
![Results Tab](assets/02_results.png)

### Chart Tab — Auto-Detected Visualization
![Chart Tab](assets/03_chart.png)

### SQL Tab — Full Generated Query, Always Visible
![SQL Tab](assets/04_sql.png)

### Explanation Tab — Plain English Business Insight
![Explanation Tab](assets/05_explanation.png)

---

## How It Works

```
You type:   "What are the top 5 merchants by fraud amount?"
                            │
                    ┌───────▼────────┐
                    │  load_schema   │  reads live DB columns — no hallucinated tables
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  generate_sql  │  GPT-4o-mini writes the SQL
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  execute_sql   │  runs against PostgreSQL
                    └───────┬────────┘
                      ┌─────┴──────┐
                   error?        success
                      │              │
              ┌───────▼──────┐       │
              │  correct_sql │       │   up to 3 retries
              └───────┬──────┘       │
                      └──────────────┘
                            │
                    ┌───────▼────────┐
                    │ explain_result │  GPT-4o-mini writes the business insight
                    └───────┬────────┘
                            │
                     Streamlit UI
             (Results | SQL | Chart | Explanation)
```

**Key design principle:** The LLM never computes numbers. Math → PostgreSQL. Interpretation → LLM. This prevents hallucinated statistics.

---

## Tech Stack

| Layer | Tool | Why This Choice |
|---|---|---|
| LLM | GPT-4o-mini | Best SQL accuracy per dollar. GPT-4 costs 20× more for marginal gain on structured queries |
| Agent | LangGraph | Stateful retry loop — if SQL fails, the graph loops back with the error message. Simple chains can't do this |
| Database | PostgreSQL | Industry standard for fintech analytics. Schema mirrors real State Street work |
| Backend | FastAPI | Async REST API with auto-generated OpenAPI docs. Clean boundary for a future Next.js frontend |
| UI | Streamlit | Chat-native interface built in hours, not days. Right tool for an analyst-built demo |
| Chat Persistence | PostgreSQL | Conversations survive browser refresh. `chat_messages` table with thread model |

---

## Features

- **Chat interface** — conversational, pinned input, full history persisted to Postgres
- **Answer cards with 4 tabs** — Results · SQL · Chart · Explanation
- **Auto-chart detection** — bar for rankings, line for time series, pie for distributions
- **Chart type override** — selectbox to switch between Bar / Line / Area / Pie / Scatter
- **CSV + Excel download** — one click from the Results tab
- **Edit & re-run SQL** — inline toggle to modify the generated query and re-execute
- **Self-correction** — agent retries up to 3 times on SQL errors, logging each attempt
- **Follow-up suggestions** — 3 LLM-generated next questions after every answer
- **Schema browser** — live table/column tree in the sidebar
- **Live dashboard** — 4 KPI metrics (customers, transactions, fraud rate, credit score) cached 5 min
- **Thread management** — create, rename, delete conversations with confirmation

---

## Database Schema

Synthetic fintech data modelled after real analyst work (200 customers, 14k+ transactions):

```
customers       → id, segment, risk_score, credit_score (FICO 300–850), country, age
accounts        → id, customer_id, account_type, balance, credit_limit, status
transactions    → id, account_id, amount, merchant, category, is_fraud, created_at
fraud_flags     → id, transaction_id, rule_triggered, confidence_score, resolution
```

Fraud rate ≈ 4%. Segments: retail (60%), premium (30%), business (10%).

---

## Local Setup

**Prerequisites:** Python 3.11+, PostgreSQL running locally, OpenAI API key

```bash
# 1. Clone and install
git clone https://github.com/Haripranay22/analystiq.git
cd analystiq
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in OPENAI_API_KEY and DATABASE_URL

# 3. Set up database
createdb analystiq
python -c "
from sqlalchemy import create_engine, text
import os; from dotenv import load_dotenv; load_dotenv()
e = create_engine(os.getenv('DATABASE_URL'))
[e.connect().execute(text(s)) for s in open('db/schema.sql').read().split(';') if s.strip()]
"
python db/seed.py   # generates 14,000+ synthetic transactions

# 4. Start the backend
uvicorn api.main:app --reload

# 5. Start the UI (new terminal)
streamlit run ui/app.py
```

Open **http://localhost:8501** and ask your first question.

---

## Project Structure

```
analystiq/
├── agent/
│   ├── graph.py        ← LangGraph wiring — 5 nodes, 1 conditional edge
│   ├── nodes.py        ← load_schema, generate_sql, execute_sql, correct_sql, explain_result
│   ├── prompts.py      ← system prompts for each LLM node
│   └── state.py        ← AgentState TypedDict (the baton passed between nodes)
│
├── api/
│   ├── main.py         ← FastAPI: /health, /query, /schema, /execute, /suggestions
│   └── models.py       ← Pydantic request/response models
│
├── ui/
│   ├── app.py          ← Streamlit chat UI
│   ├── api_client.py   ← thin HTTP layer — all API calls in one place
│   └── db.py           ← chat persistence (threads + messages CRUD)
│
├── db/
│   ├── schema.sql      ← PostgreSQL schema (4 tables + chat history)
│   └── seed.py         ← synthetic fintech data generator (Faker + SQLAlchemy)
│
└── tests/
    └── test_agent.py   ← routing logic tests (no DB/OpenAI required)
```

---

## API Endpoints

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/health` | Liveness check + DB connectivity |
| `POST` | `/query` | Full agent pipeline — returns SQL, results, explanation, elapsed_ms |
| `GET` | `/schema` | Live DB schema (cached in memory) |
| `POST` | `/execute` | Run edited SQL (SELECT-only guard + read-only DB role) |
| `POST` | `/suggestions` | 3 LLM-generated follow-up questions |

Interactive docs at **http://localhost:8000/docs** when the API is running.

---

## Interview Talking Points

**"Why LangGraph instead of a simple chain?"**
The self-correction loop is stateful — if SQL execution fails, the graph routes back to `correct_sql` with the exact error message. A simple chain runs top-to-bottom and can't loop. LangGraph's conditional edges make retry logic explicit and debuggable.

**"How do you prevent hallucinations?"**
Two layers: (1) `load_schema` reads the live database schema before every query — the LLM never guesses column names. (2) LLMs only write narrative text, never compute numbers. All arithmetic happens in PostgreSQL.

**"What would this look like at scale?"**
Swap local PostgreSQL for Snowflake (schema.sql is Snowflake-compatible), add dbt for metric definitions, point Power BI at the same warehouse. The FastAPI backend is the stable contract — the UI can be replaced with Next.js without touching the agent.

**"Why gpt-4o-mini and not GPT-4?"**
SQL generation is a structured, well-defined task. gpt-4o-mini achieves the same accuracy on 95% of queries at 1/20th the cost. The agent retries on failure — good enough beats expensive.

---

## Built By

**Haripranay Peddagolla**
Senior Data Analyst · 4+ years fintech · MS Data Science, UT Arlington
State Street · KPIT Technologies

*This project is the proof that an analyst can ship AI-powered data tools — not just consume them.*
