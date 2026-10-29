"""Local plant database (SQLite, fully offline).

Stores the ideal temperature (°C) and relative humidity (%) range for
each plant. The ranges below are general starting values for a
greenhouse and should be double-checked before anyone relies on them.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("plants.db")

# name, min_temp, max_temp, min_hum, max_hum, notes
SEED_PLANTS = [
    ("Tomato",     18, 27, 50, 70, "Fruit set suffers above ~30 °C."),
    ("Cucumber",   21, 27, 60, 80, "Likes it warm and humid."),
    ("Bell Pepper",21, 29, 50, 70, "Sensitive to cold nights."),
    ("Lettuce",    15, 21, 50, 70, "Bolts (goes to seed) in heat."),
    ("Spinach",    10, 21, 50, 60, "Prefers cool conditions."),
    ("Basil",      18, 29, 40, 60, "Damaged by cold; avoid very high humidity."),
    ("Mint",       18, 24, 40, 60, "Tolerant, but keep it out of extreme heat."),
    ("Strawberry", 15, 26, 60, 75, "Good airflow helps prevent mold."),
    ("Orchid",     18, 29, 50, 70, "Based on common moth orchids (Phalaenopsis)."),
    ("Cactus",     18, 32,10, 40, "Needs dry air; humidity is the main risk."),
]


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the table and fill it on first run."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plants (
                name     TEXT PRIMARY KEY COLLATE NOCASE,
                min_temp REAL NOT NULL,
                max_temp REAL NOT NULL,
                min_hum  REAL NOT NULL,
                max_hum  REAL NOT NULL,
                notes    TEXT
            )
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO plants VALUES (?, ?, ?, ?, ?, ?)",
            SEED_PLANTS,
        )


def list_plants():
    """All plant names, alphabetical."""
    with _connect() as conn:
        rows = conn.execute("SELECT name FROM plants ORDER BY name").fetchall()
    return [r["name"] for r in rows]


def get_plant(name):
    """Return a plant as a dict, or None if it isn't in the database."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM plants WHERE name = ?", (name.strip(),)
        ).fetchone()
    return dict(row) if row else None


def check_conditions(plant, temperature, humidity):
    """Compare current readings to a plant's ideal ranges.

    Returns (ok, messages). `plant` is a dict from get_plant().
    """
    messages = []
    if temperature < plant["min_temp"]:
        messages.append(f"Too cold ({temperature:.1f} °C, want {plant['min_temp']:.0f}-{plant['max_temp']:.0f})")
    elif temperature > plant["max_temp"]:
        messages.append(f"Too hot ({temperature:.1f} °C, want {plant['min_temp']:.0f}-{plant['max_temp']:.0f})")

    if humidity < plant["min_hum"]:
        messages.append(f"Too dry ({humidity:.1f}%, want {plant['min_hum']:.0f}-{plant['max_hum']:.0f}%)")
    elif humidity > plant["max_hum"]:
        messages.append(f"Too humid ({humidity:.1f}%, want {plant['min_hum']:.0f}-{plant['max_hum']:.0f}%)")

    return (len(messages) == 0, messages)


if __name__ == "__main__":
    # Quick self-test: python3 plant_db.py
    init_db()
    print("Plants:", ", ".join(list_plants()))
    tomato = get_plant("tomato")
    print("Tomato:", tomato)
    print("Check 24 °C / 60%:", check_conditions(tomato, 24, 60))
    print("Check 33 °C / 85%:", check_conditions(tomato, 33, 85))
