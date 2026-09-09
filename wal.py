import os


class WAL:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(filename):
            open(filename, 'a').close()
        self.file = open(filename, 'a')

    def append(self, id, name):
        line = f"INSERT|{id}|{name}\n"
        self.file.write(line)
        self.file.flush()
        os.fsync(self.file.fileno())

    def read_all(self):
        with open(self.filename, 'r') as f:
            lines = [l.rstrip('\n') for l in f if l.strip()]
        entries = []
        for line in lines:
            op, id_str, name = line.split('|')
            entries.append((op, int(id_str), name))
        return entries

    def close(self):
        self.file.close()
