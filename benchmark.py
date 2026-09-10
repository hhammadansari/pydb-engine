"""
For each table size, we measure:
  - full_scan:    SELECT ... WHERE name = 'nonexistent'  (forces reading every row)
  - index_lookup: SELECT ... WHERE id = <last row's id>  (worst case for a B+ tree: deepest key)
"""

import os
import time
from engine import Database

SIZES = [100, 500, 1000, 3000, 6000, 12000]
REPEATS_INDEX = 20   # index lookups are fast; average several runs for a stable number
REPEATS_SCAN = 3      # full scans are slow; a few runs is enough


def build_table(n):
    for f in ('bench.db', 'bench.db.wal', 'bench.db.meta'):
        if os.path.exists(f):
            os.remove(f)
    db = Database()
    db.create_table('users', 'bench.db', index_order=64)
    for i in range(n):
        db.execute(f"INSERT INTO users VALUES ({i}, 'user{i}')")
    return db


def time_it(fn, repeats):
    start = time.perf_counter()
    for _ in range(repeats):
        fn()
    elapsed = time.perf_counter() - start
    return (elapsed / repeats) * 1000  # ms per run


results = []
for n in SIZES:
    db = build_table(n)
    last_id = n - 1

    scan_ms = time_it(
        lambda: db.execute("SELECT * FROM users WHERE name = 'nonexistent'"),
        REPEATS_SCAN,
    )
    index_ms = time_it(
        lambda: db.execute(f"SELECT name FROM users WHERE id = {last_id}"),
        REPEATS_INDEX,
    )

    results.append((n, scan_ms, index_ms))
    print(f"n={n:>6}   full_scan={scan_ms:8.3f} ms   index_lookup={index_ms:7.4f} ms   "
          f"ratio={scan_ms / index_ms:8.1f}x")

    db.close()

print("\nRaw results (rows, full_scan_ms, index_lookup_ms):")
for row in results:
    print(row)
