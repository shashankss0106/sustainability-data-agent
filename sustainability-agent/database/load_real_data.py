"""
load_real_data.py
------------------
Loads the real data-center sustainability CSV (data_center_hybrid.csv)
into the SQLite database the agent queries against.

This replaces the synthetic demo data from setup_db.py with your actual
126,770-row dataset -- same data used in the Power BI dashboard.

Run this once:
    python database/load_real_data.py
"""

import os
import sqlite3
import pandas as pd

HERE = os.path.dirname(__file__)
CSV_PATH = os.path.join(HERE, "data_center_hybrid.csv")
DB_PATH = os.path.join(HERE, "sustainability.db")


def load():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"Could not find {CSV_PATH}. Place data_center_hybrid.csv in the "
            "database/ folder before running this script."
        )

    df = pd.read_csv(CSV_PATH)
    conn = sqlite3.connect(DB_PATH)

    # Table name matches what agent.py expects: facility_metrics
    df.to_sql("facility_metrics", conn, if_exists="replace", index=False)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM facility_metrics")
    count = cur.fetchone()[0]
    conn.close()

    print(f"Loaded {count} rows into {DB_PATH} (table: facility_metrics)")


if __name__ == "__main__":
    load()
