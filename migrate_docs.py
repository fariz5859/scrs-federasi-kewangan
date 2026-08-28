"""Add doc_msc and doc_perjanjian_pembelian columns to case table."""
import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'ssps.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check existing columns
cur.execute("PRAGMA table_info('case')")
cols = {row[1] for row in cur.fetchall()}

# Remove old column reference if needed, add new ones
for col in ['doc_msc', 'doc_perjanjian_pembelian']:
    if col not in cols:
        cur.execute(f"ALTER TABLE 'case' ADD COLUMN {col} VARCHAR(300)")
        print(f"  + Added column: {col}")
    else:
        print(f"  = Column already exists: {col}")

# Drop old column if it exists (SQLite 3.35+)
if 'document_path' in cols:
    try:
        cur.execute("ALTER TABLE 'case' DROP COLUMN document_path")
        print("  - Dropped old column: document_path")
    except Exception:
        print("  ~ Could not drop document_path (SQLite too old, harmless)")

conn.commit()
conn.close()
print("\nDone! Restart Flask to pick up changes.")
