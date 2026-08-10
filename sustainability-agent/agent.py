"""
agent.py
--------
Sustainability Data Agent

BUSINESS PURPOSE
-----------------
Sustainability and operations teams often need answers from facility data
(energy use, PUE, renewable mix, emissions) but don't write SQL themselves.
Today that means filing a request and waiting on an analyst. This agent
closes that gap: a stakeholder asks a plain-English question, the agent
figures out what data is needed, writes and runs the SQL itself, checks
its own result, and returns a direct answer -- self-service analytics
instead of an analyst queue.

HOW IT WORKS
------------
The agent is given two tools, not a fixed set of pre-written queries:
  1. get_schema()        -> lets the agent inspect the table structure itself
  2. run_sql_query(sql)  -> lets the agent execute the query it writes

This is the core pattern that makes it "agentic" rather than a script:
the model decides which tool to call, in what order, and how many times,
based on the question -- it is not a hardcoded if/else router.

USAGE
-----
    export ANTHROPIC_API_KEY="your-key-here"
    python agent.py "Which facility improved renewable energy the most in 2025?"

    # or run interactively
    python agent.py
"""

import os
import sys
import json
import sqlite3

from anthropic import Anthropic

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "sustainability.db")
MODEL = "claude-sonnet-4-6"

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

TOOLS = [
    {
        "name": "get_schema",
        "description": "Returns the column names and types of the facility_metrics table.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql_query",
        "description": (
            "Executes a read-only SQL SELECT query against the facility_metrics "
            "table and returns the resulting rows as JSON."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT statement to run.",
                }
            },
            "required": ["sql"],
        },
    },
]


def get_schema() -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(facility_metrics)")
    cols = cur.fetchall()
    conn.close()
    schema = [{"column": c[1], "type": c[2]} for c in cols]
    return json.dumps({"table": "facility_metrics", "columns": schema})


def run_sql_query(sql: str) -> str:
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


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "get_schema":
        return get_schema()
    if name == "run_sql_query":
        return run_sql_query(tool_input.get("sql", ""))
    return json.dumps({"error": f"Unknown tool: {name}"})


def ask_agent(question: str, verbose: bool = True) -> str:
    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment

    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # Final answer -- extract and return the text
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if verbose:
                    print(f"  [agent called {block.name}] input={block.input}")
                result = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "user", "content": tool_results})


def main():
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python database/setup_db.py")
        sys.exit(1)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"Q: {question}\n")
        answer = ask_agent(question)
        print(f"\nA: {answer}")
    else:
        print("Sustainability Data Agent -- type a question, or 'quit' to exit.\n")
        while True:
            question = input("Q: ").strip()
            if question.lower() in {"quit", "exit"}:
                break
            answer = ask_agent(question)
            print(f"\nA: {answer}\n")


if __name__ == "__main__":
    main()
