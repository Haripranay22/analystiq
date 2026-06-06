# AnalystIQ — AI Copilot for Data Analysts

## What this product is
AnalystIQ makes Data Analysts faster by letting them (and their stakeholders) ask
questions in plain English and getting back SQL, results, explanations, and charts —
instantly. Built by a Data Analyst, for Data Analysts.

## Who is building this
Haripranay Peddagolla — Senior Data Analyst with 4+ years in fintech.
Not an AI engineer. An analyst who ships AI-powered data tools.

## Current Phase
**PHASE 0 COMPLETE — Project Foundation**
**PHASE 1 COMPLETE — Database Layer**
**PHASE 2 COMPLETE — LangGraph Agent Core**
**PHASE 3 NEXT — FastAPI Backend**

## Stack & Why
| Layer       | Tool              | Why                                              |
|-------------|-------------------|--------------------------------------------------|
| LLM         | OpenAI gpt-4o-mini | Budget-friendly, fast, great at SQL generation  |
| Agent       | LangGraph         | Structured agent with visible nodes — learnable  |
| Database    | PostgreSQL (local) | Industry standard, matches real analyst work     |
| Backend     | FastAPI           | Async, clean REST API, easy to extend            |
| UI          | Streamlit         | Fast to build, looks good in demos               |
| Env vars    | python-dotenv     | Never hardcode secrets                           |

## Model Usage Rules (stay budget-friendly)
- Default: `gpt-4o-mini` for all SQL generation and explanations
- Only use `gpt-4o` if mini fails on complex multi-join queries
- Never use GPT-4 Turbo — unnecessary cost

## Project Structure
```
analystiq/
├── CLAUDE.md              ← This file. Update after every phase decision.
├── .env.example           ← Template for environment variables
├── requirements.txt       ← All dependencies, pinned versions
├── run.py                 ← CLI test runner (use before UI is built)
│
├── db/
│   ├── schema.sql         ← Fintech PostgreSQL schema
│   └── seed.py            ← Generates realistic synthetic fintech data
│
├── agent/
│   ├── state.py           ← AgentState TypedDict (the baton)
│   ├── prompts.py         ← System prompts for each LLM node
│   ├── nodes.py           ← 5 node functions (the workers)
│   └── graph.py           ← LangGraph wiring (the map)
│
├── api/                   ← Phase 3: FastAPI routes live here
├── ui/                    ← Phase 4: Streamlit app lives here
└── tests/
    └── test_agent.py      ← Routing logic tests (no DB/OpenAI needed)
```

## Database: Fintech Schema
Tables we work with (mirrors real analyst work at State Street):
- `customers` — customer profiles, segments, risk scores
- `accounts` — account types, balances, credit limits
- `transactions` — payments, amounts, merchants, fraud flags
- `fraud_flags` — which rule triggered, confidence score

## Decisions Made (update as we build)
- [Phase 0] Using local PostgreSQL, not cloud — keeps costs at zero during dev
- [Phase 0] Using python-dotenv for env management
- [Phase 0] gpt-4o-mini as default model
- [Phase 2] MAX_RETRIES = 3 for self-correction loop
- [Phase 2] Results stored as JSON string in state (handles Decimal/datetime via default=str)
- [Phase 2] Module-level LLM and engine instances — avoid re-initializing on every node call
- [Phase 2] Explainer receives only first 10 rows to keep token usage low

## What NOT to do
- Do NOT hardcode API keys anywhere
- Do NOT use gpt-4 or gpt-4-turbo (expensive, unnecessary)
- Do NOT skip tests — one test per phase minimum
- Do NOT move to next phase until current phase is understood
- Do NOT add features not in the current phase scope
