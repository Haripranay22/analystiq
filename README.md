# AnalystIQ — AI Copilot for Data Analysts

Ask questions in plain English. Get SQL, results, explanations, and charts back instantly.

Built by a Data Analyst, for Data Analysts.

## Tech Stack
- **LLM**: OpenAI gpt-4o-mini
- **Agent**: LangGraph
- **Database**: PostgreSQL
- **Backend**: FastAPI
- **UI**: Streamlit

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your OpenAI key and PostgreSQL credentials

# 4. Set up PostgreSQL database
createdb analystiq
psql -U postgres -d analystiq -f db/schema.sql

# 5. Seed with synthetic fintech data
python db/seed.py
```

## Build Phases
- [x] Phase 0 — Project Foundation
- [x] Phase 1 — Database Layer (schema + seed data)
- [ ] Phase 2 — LangGraph Agent Core
- [ ] Phase 3 — FastAPI Backend
- [ ] Phase 4 — Streamlit UI
- [ ] Phase 5 — Intelligence Layer
- [ ] Phase 6 — Deploy
