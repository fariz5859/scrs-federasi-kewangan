"""Add per-case flag columns to case table."""
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'ssps.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info('case')")
cols = {row[1] for row in cur.fetchall()}

new_cols = {
    'koseri_flag':          'VARCHAR(20)',
    'koseri_flag_reason':   'TEXT',
    'fedkew_response':      'VARCHAR(20)',
    'fedkew_response_note': 'TEXT',
}

for col, dtype in new_cols.items():
    if col not in cols:
        cur.execute(f"ALTER TABLE 'case' ADD COLUMN {col} {dtype}")
        print(f"  + Added column: {col}")
    else:
        print(f"  = Column already exists: {col}")

conn.commit()
conn.close()
print("\nDone! Restart Flask to pick up changes.")
