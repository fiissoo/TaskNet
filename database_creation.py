import sqlite3

conn = sqlite3.connect('tasknest.db')
cursor = conn.cursor()

# Only run this once! It will fail if column already exists
try:
    cursor.execute("ALTER TABLE task ADD COLUMN notes TEXT")
    print("✅ Column 'notes' added.")
except sqlite3.OperationalError as e:
    print("⚠️", e)

conn.commit()
conn.close()
