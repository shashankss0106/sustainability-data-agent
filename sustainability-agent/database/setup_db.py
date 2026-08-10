"""
setup_db.py
-----------
Generates a synthetic but realistic data-center sustainability dataset
and loads it into a local SQLite database (sustainability.db).

Schema: facility_metrics
  - id                    INTEGER PRIMARY KEY
  - facility_name         TEXT
  - region                TEXT
  - report_month          TEXT   (YYYY-MM)
  - it_load_mw            REAL   (IT equipment load, megawatts)
  - energy_consumption_mwh REAL  (total facility energy draw, MWh)
  - renewable_energy_pct  REAL   (% of energy from renewable sources)
  - pue                   REAL   (Power Usage Effectiveness, lower is better)
  - carbon_emissions_tco2e REAL  (tonnes CO2-equivalent)
  - water_usage_liters    REAL   (total water usage, litres)

Run this once to (re)build the database:
    python database/setup_db.py
"""

import sqlite3
import random
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sustainability.db")

FACILITIES = [
    ("Facility Alpha", "APAC"),
    ("Facility Beta", "APAC"),
    ("Facility Gamma", "EMEA"),
    ("Facility Delta", "EMEA"),
    ("Facility Epsilon", "North America"),
    ("Facility Zeta", "North America"),
]

MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 7)]

# Region-level baselines so the data tells a believable, non-random story
REGION_BASELINE = {
    "APAC": {"renewable": 28, "pue": 1.55},
    "EMEA": {"renewable": 46, "pue": 1.40},
    "North America": {"renewable": 35, "pue": 1.48},
}


def generate_rows():
    random.seed(42)
    rows = []
    for facility_name, region in FACILITIES:
        base = REGION_BASELINE[region]
        # Each facility improves gradually over time (renewables up, PUE down)
        renewable_start = base["renewable"] + random.uniform(-4, 4)
        pue_start = base["pue"] + random.uniform(-0.08, 0.08)
        it_load = random.uniform(8, 22)  # MW, roughly fixed per facility

        for i, month in enumerate(MONTHS):
            renewable_pct = min(95, renewable_start + i * random.uniform(0.6, 1.3))
            pue = max(1.08, pue_start - i * random.uniform(0.005, 0.015))
            energy_mwh = it_load * pue * 24 * 30 * random.uniform(0.95, 1.05)
            emissions = energy_mwh * (1 - renewable_pct / 100) * 0.42  # tCO2e factor
            water_liters = energy_mwh * random.uniform(180, 260)

            rows.append((
                facility_name,
                region,
                month,
                round(it_load, 2),
                round(energy_mwh, 2),
                round(renewable_pct, 2),
                round(pue, 3),
                round(emissions, 2),
                round(water_liters, 2),
            ))
    return rows


def build_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE facility_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT NOT NULL,
            region TEXT NOT NULL,
            report_month TEXT NOT NULL,
            it_load_mw REAL,
            energy_consumption_mwh REAL,
            renewable_energy_pct REAL,
            pue REAL,
            carbon_emissions_tco2e REAL,
            water_usage_liters REAL
        )
    """)

    rows = generate_rows()
    cur.executemany("""
        INSERT INTO facility_metrics
        (facility_name, region, report_month, it_load_mw, energy_consumption_mwh,
         renewable_energy_pct, pue, carbon_emissions_tco2e, water_usage_liters)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    print(f"Created {DB_PATH} with {len(rows)} rows across {len(FACILITIES)} facilities.")
    conn.close()


if __name__ == "__main__":
    build_database()
