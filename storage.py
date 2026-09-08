"""
Page-based fixed-size record storage.

    page_number = index // records_per_page
    slot        = index %  records_per_page
    byte_offset = page_number * PAGE_SIZE + HEADER_SIZE + slot * RECORD_SIZE
"""

import struct
import os

PAGE_SIZE = 4096

RECORD_FORMAT = '>I20s'     # id (4 bytes) + name (20 bytes)
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)

HEADER_FORMAT = '>H'        # record_count (2 bytes, up to 65535)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

RECORDS_PER_PAGE = (PAGE_SIZE - HEADER_SIZE) // RECORD_SIZE


class Page:
    """In-memory representation of one page's contents."""

    def __init__(self, record_count=0, records=None):
        self.record_count = record_count
        self.records = records if records is not None else [] 

    def to_bytes(self):
        buf = bytearray(PAGE_SIZE) 
        struct.pack_into(HEADER_FORMAT, buf, 0, self.record_count)

        offset = HEADER_SIZE
        for (id, name) in self.records:
            name_bytes = name.encode('utf-8')[:20].ljust(20, b'\x00')
            struct.pack_into(RECORD_FORMAT, buf, offset, id, name_bytes)
            offset += RECORD_SIZE

        return bytes(buf)

    @classmethod
    def from_bytes(cls, data):
        record_count = struct.unpack_from(HEADER_FORMAT, data, 0)[0]
        records = []
        offset = HEADER_SIZE
        for _ in range(record_count):
            id, name_bytes = struct.unpack_from(RECORD_FORMAT, data, offset)
            name = name_bytes.rstrip(b'\x00').decode('utf-8')
            records.append((id, name))
            offset += RECORD_SIZE
        return cls(record_count, records)


class PagedStore:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(filename):
            open(filename, 'wb').close()
        self.file = open(filename, 'r+b')

    def page_count(self):
        self.file.seek(0, os.SEEK_END)
        return self.file.tell() // PAGE_SIZE

    def read_page(self, page_number):
        offset = page_number * PAGE_SIZE
        self.file.seek(offset)
        data = self.file.read(PAGE_SIZE)
        if len(data) < PAGE_SIZE:
            return Page()  
        return Page.from_bytes(data)

    def write_page(self, page_number, page):
        offset = page_number * PAGE_SIZE
        self.file.seek(offset)
        self.file.write(page.to_bytes())
        self.file.flush()

    def insert(self, id, name):
        """Append a record to the last page, or start a new page if full."""
        pc = self.page_count()

        if pc == 0:
            page_number, page = 0, Page()
        else:
            page_number = pc - 1
            page = self.read_page(page_number)
            if page.record_count >= RECORDS_PER_PAGE:
                page_number, page = pc, Page() 

        index = page_number * RECORDS_PER_PAGE + page.record_count  # global row index
        page.records.append((id, name))
        page.record_count += 1
        self.write_page(page_number, page)
        return index

    def get(self, index):
        """Fetch record #index using page/slot addressing — no scanning."""
        page_number = index // RECORDS_PER_PAGE   
        slot = index % RECORDS_PER_PAGE           

        page = self.read_page(page_number)
        if slot >= page.record_count:
            raise IndexError(f"No record at index {index}")

        id, name = page.records[slot]
        return {'id': id, 'name': name}

    def close(self):
        self.file.close()


if __name__ == '__main__':
    if os.path.exists('users.db'):
        os.remove('users.db')

    print(f"RECORD_SIZE = {RECORD_SIZE} bytes")
    print(f"RECORDS_PER_PAGE = {RECORDS_PER_PAGE}")

    store = PagedStore('users.db')
    store.insert(1, 'Hamoody')
    store.insert(2, 'Balwindar')
    store.insert(500, 'Fransis')
    store.insert(501, 'Shams')

    print("Record at index 2:", store.get(2))
    print("Total pages on disk:", store.page_count())

    store.close()
