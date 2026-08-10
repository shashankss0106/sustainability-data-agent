"""
agent_gemini.py
----------------
Sustainability Data Agent -- Gemini API version

Same agent, same database, same business purpose as agent.py --
this version calls Google's Gemini API instead of Anthropic's Claude API,
because Gemini's free tier requires no credit card.

IMPORTANT: if you use this version, update your CV wording. agent.py's
CV description says "Claude's tool use API" -- this file uses Gemini's
function calling instead. Keep whichever one you actually ran and can
demo matching what your CV says. Don't leave both descriptions on the
CV if only one was actually executed.

SETUP
-----
    pip install google-genai
    Get a free API key at https://aistudio.google.com/apikey (no card required)

USAGE
-----
    set GOOGLE_API_KEY=your-key-here      (Windows cmd)
    python agent_gemini.py "your question here"
"""

import os
import sys
import json
import sqlite3

from google import genai
from google.genai import types

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "sustainability.db")

# Google's free-tier model lineup changes frequently (several models were
# deprecated or moved behind billing during 2026 alone). Instead of hardcoding
# one name that can go stale, try a short list of current/likely-free
# candidates in order and use the first one that actually responds.
CANDIDATE_MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

SYSTEM_PROMPT = """You are a Sustainability Data Agent for a data-center operator.
You answer plain-English questions from operations and sustainability
stakeholders using the facility_metrics table.

Rules:
- Always call get_schema before writing SQL if you have not seen the schema yet.
- Only ever write SELECT statements. Never modify data.
- After you get query results, explain the answer in plain business language.
  Do not just dump a table -- interpret it (trend, comparison, standout facility, etc).
- If a question is ambiguous, make a reasonable assumption and say what you assumed.
"""


def get_schema() -> str:
    """Returns the column names and types of the facility_metrics table.

    Returns:
        A JSON string describing the table's columns and their types.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(facility_metrics)")
    cols = cur.fetchall()
    conn.close()
    schema = [{"column": c[1], "type": c[2]} for c in cols]
    return json.dumps({"table": "facility_metrics", "columns": schema})


def run_sql_query(sql: str) -> str:
    """Executes a read-only SQL SELECT query against the facility_metrics table.

    Args:
        sql: A single SELECT statement to run. Only SELECT is permitted.

    Returns:
        A JSON string with the row count and resulting rows.
    """
    if not sql.strip().lower().startswith("select"):
        return json.dumps({"error": "Only SELECT statements are permitted."})
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql)
        col_names = [d[0] for d in cur.description]
        rows = cur.fetchall()
        conn.close()
        results = [dict(zip(col_names, row)) for row in rows]
        return json.dumps({"row_count": len(results), "rows": results[:50]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def ask_agent(question: str) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable not set. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    client = genai.Client(api_key=api_key)

    last_error = None
    for model_name in CANDIDATE_MODELS:
        try:
            # Passing the real Python functions directly as tools -- the SDK
            # generates the schema from each function's signature/docstring
            # and automatically executes them when the model requests a
            # call, then feeds the result back in to produce the final answer.
            response = client.models.generate_content(
                model=model_name,
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[get_schema, run_sql_query],
                ),
            )
            print(f"  [using model: {model_name}]")
            return response.text
        except Exception as e:
            last_error = e
            print(f"  [{model_name} unavailable ({type(e).__name__}), trying next...]")
            continue

    raise RuntimeError(
        f"None of the candidate models worked. Last error: {last_error}\n"
        "Check https://ai.google.dev/gemini-api/docs/models for current free-tier model names "
        "and add the right one to CANDIDATE_MODELS at the top of this file."
    )


def main():
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python database/load_real_data.py")
        sys.exit(1)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"Q: {question}\n")
        answer = ask_agent(question)
        print(f"A: {answer}")
    else:
        print("Sustainability Data Agent (Gemini) -- type a question, or 'quit' to exit.\n")
        while True:
            question = input("Q: ").strip()
            if question.lower() in {"quit", "exit"}:
                break
            answer = ask_agent(question)
            print(f"A: {answer}\n")


if __name__ == "__main__":
    main()
