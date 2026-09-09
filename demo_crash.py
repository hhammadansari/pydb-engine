"""
Simulates the exact failure window WAL is designed for: a write gets
logged, then the process dies BEFORE that write is applied to storage.
We then "restart" the database and prove the write survives anyway.
"""

import os
from engine import Database

for f in ('users.db', 'users.db.wal', 'users.db.meta'):
    if os.path.exists(f):
        os.remove(f)

print("=== Session 1: normal operation ===")
db = Database()
db.create_table('users', 'users.db')
db.execute("INSERT INTO users VALUES (1, 'Hamoody')")
db.execute("INSERT INTO users VALUES (2, 'Balwinder')")
print("Rows after normal inserts:", db.execute("SELECT * FROM users"))

print("\n=== Simulating a crash ===")
table = db.tables['users']
table.wal.append(999, 'Ghost')  # logged
print("Logged id=999 to the WAL, but skipping storage.insert() and the index update.")
print("This is exactly what a crash right after fsync would look like.")

print("\n=== Session 2: 'restart' by opening the database fresh ===")
db2 = Database()
db2.create_table('users', 'users.db') 

print("\nQuerying for the 'crashed' row:")
result = db2.execute("SELECT * FROM users WHERE id = 999")
print("SELECT * FROM users WHERE id = 999 ->", result)

assert result == [{'id': 999, 'name': 'Ghost'}], "Recovery failed to restore the write!"
print("\n✓ The logged-but-unapplied write survived the simulated crash.")

db2.close()
