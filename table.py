"""
Table = PagedStore (source of truth, on disk)
      + WAL (durability: survives crashes between log and apply)
      + BPlusTree (derived index, in memory, rebuilt on startup)

Startup order:
    1. Open storage.
    2. Recover: replay any WAL entries not yet reflected in storage.
    3. Rebuild the index by scanning storage ONCE, now that it's
       guaranteed to be complete and consistent.
"""

from storage import PagedStore, RECORDS_PER_PAGE
from btree import BPlusTree
from wal import WAL
import os


class Table:
    def __init__(self, name, data_filename, wal_filename=None, meta_filename=None, index_order=32):
        self.name = name
        self.storage = PagedStore(data_filename)
        self.wal = WAL(wal_filename or (data_filename + '.wal'))
        self.meta_filename = meta_filename or (data_filename + '.meta')
        self._row_count_cache = None

        self._recover()

        self.index = BPlusTree(order=index_order)
        self._rebuild_index()

    def _read_applied_count(self):
        if not os.path.exists(self.meta_filename):
            return 0
        with open(self.meta_filename) as f:
            content = f.read().strip()
            return int(content) if content else 0

    def _write_applied_count(self, count):
        with open(self.meta_filename, 'w') as f:
            f.write(str(count))
            f.flush()
            os.fsync(f.fileno())

    def _recover(self):
        applied = self._read_applied_count()
        entries = self.wal.read_all()
        if len(entries) > applied:
            unapplied = entries[applied:]
            print(f"[recovery] {len(unapplied)} unapplied WAL entr"
                  f"{'y' if len(unapplied) == 1 else 'ies'} found - replaying...")
            for (_op, id, name) in unapplied:
                self.storage.insert(id, name)
            self._write_applied_count(len(entries))

    def _rebuild_index(self):
        for page_num in range(self.storage.page_count()):
            page = self.storage.read_page(page_num)
            for slot in range(page.record_count):
                id, _name = page.records[slot]
                row_index = page_num * RECORDS_PER_PAGE + slot
                self.index.insert(id, row_index)

    def insert(self, id, name):
        self.wal.append(id, name)                       
        row_index = self.storage.insert(id, name)        
        self.index.insert(id, row_index)                 
        self._write_applied_count(self._read_applied_count() + 1)  
        self._row_count_cache = None
        return row_index

    def row_count(self):
        if self._row_count_cache is None:
            total = 0
            for p in range(self.storage.page_count()):
                total += self.storage.read_page(p).record_count
            self._row_count_cache = total
        return self._row_count_cache

    def full_scan(self):
        for row_index in range(self.row_count()):
            yield self.storage.get(row_index)

    def index_lookup(self, id):
        row_index = self.index.search(id)
        if row_index is None:
            return None
        return self.storage.get(row_index)

    def close(self):
        self.storage.close()
        self.wal.close()
