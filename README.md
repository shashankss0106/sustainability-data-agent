# Sustainability Data Agent

An agentic AI system that lets a non-technical stakeholder ask plain-English
questions about data-center sustainability metrics and get a direct,
data-grounded answer — no SQL required.

## Business problem

Operations and sustainability teams routinely need answers from facility
data (energy use, renewable mix, emissions, PUE) but don't write SQL
themselves. Today that means submitting a request and waiting on an
analyst to pull the numbers. This agent removes that bottleneck: it
interprets the question, decides what data it needs, writes and runs the
query itself, and returns the answer in business language — self-service
analytics instead of an analyst queue.

This mirrors the exact use case behind conversational-analytics products
that consulting and analytics firms (Deloitte, ZS Associates, Mu Sigma,
EXL) build and sell to clients — reducing the distance between "I have a
question" and "I have an answer."

## Why this is "agentic", not just a script

The agent is given two tools — `get_schema` and `run_sql_query` — not a
fixed set of pre-written queries. The model itself decides:
- whether it needs to check the schema first
- what SQL to write for a given question
- whether the result actually answers the question, or whether it needs
  to run a follow-up query

That decision-making loop (not a hardcoded `if question contains "emissions"`
router) is what makes it an agent rather than a wrapper script.

## Architecture

```
User question (plain English)
        │
        ▼
   Gemini (Flash) ── decides which tool to call
        │
        ├── get_schema()        → inspects facility_metrics table structure
        │
        └── run_sql_query(sql)  → executes a SELECT against SQLite,
                                   returns rows as JSON
        │
        ▼
Claude interprets the result and returns a plain-language answer
```

**Guardrail:** `run_sql_query` rejects anything that isn't a `SELECT`
statement, so the agent can read data but never modify it — a basic but
important safety boundary for any agent given database access.

## Tech stack

- **Gemini (Flash 2.5 API)** — reasoning and tool-use loop
- **SQLite** — lightweight database, `facility_metrics` table
- **Python** — orchestration, no additional agent framework required

## Dataset

`database/data_center_hybrid.csv` — 126,770 rows across 18,110 facilities
(2019–2025), with columns for facility type, cooling system, PUE (power
usage effectiveness), WUE (water usage effectiveness), electricity/water
usage, and surrounding water stress tier. This is the same dataset used
in the companion Power BI dashboard.

`database/load_real_data.py` loads this CSV into `sustainability.db`
(table: `facility_metrics`) that the agent queries against.

> The agent doesn't have any dataset-specific logic hardcoded — it calls
> `get_schema` to discover whatever columns exist, then writes SQL
> against them. Point it at a different CSV/database and it adapts
> automatically.

## Setup

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY="your-key-here"   
python database/load_real_data.py          # builds database/sustainability.db from the real CSV
python agent.py "your question here"
```

Or run it interactively with no arguments: `python agent.py`

**Example questions to try:**
- "Which cooling system type has the best average PUE?"
- "Do facilities in high water-stress regions use water more efficiently than those in low-stress regions?"
- "Compare average PUE across facility types."

## Example usage

These queries were run directly against the real 126,770-row dataset to
verify the agent's tools produce correct results end-to-end.

**Q: Which cooling system type has the best average PUE?**

| Cooling System | Avg PUE |
|---|---|
| Liquid Cooled | **1.337** |
| Evaporative | 1.592 |
| Air Cooled | 1.670 |

→ *Liquid-cooled facilities run roughly 20% more power-efficient than
air-cooled ones (lower PUE is better; 1.0 is theoretical perfect
efficiency).*

**Q: Do facilities in high water-stress regions use water more efficiently?**

| Water Stress Tier | Avg WUE (L/kWh) |
|---|---|
| High | 0.831 |
| Medium | 0.816 |
| Low | 0.813 |

→ *No — high water-stress regions show no meaningful improvement in
water efficiency over low-stress regions, despite facing greater
environmental pressure to conserve. This is the more interesting,
counterintuitive finding of the two.*

## Honest scope note

This is a working proof-of-concept, not a production system: no auth
layer, no rate limiting, no multi-user support, and it's validated
against a synthetic dataset rather than a live production database. What
it does demonstrate cleanly is the core agentic pattern — an LLM given
tools to inspect a schema and query a database on its own, rather than
answering from a fixed set of pre-written queries.

## Possible extensions

- Point it at a real production database (Postgres/MySQL) via the same
  `get_schema` / `run_sql_query` tool pattern
- Add a `create_chart` tool so the agent can return a visualization, not
  just text
- Add conversation memory so follow-up questions ("now break that down
  by region") work without repeating context
- Wrap in a Streamlit or Slack-bot front end for actual stakeholder use
