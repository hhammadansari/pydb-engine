import os
from table import Table
from query import parse, make_plan, execute_select


class Database:
    def __init__(self):
        self.tables = {}

    def create_table(self, name, filename, index_order=32):
        self.tables[name] = Table(name, filename, index_order=index_order)

    def execute(self, sql):
        ast = parse(sql)

        if ast['type'] == 'insert':
            table = self.tables[ast['table']]
            id, name = ast['values']
            row_index = table.insert(id, name)
            return f"Inserted id={id} at row_index={row_index}"

        elif ast['type'] == 'select':
            table = self.tables[ast['table']]
            plan = make_plan(ast)
            return execute_select(plan, table)

        raise ValueError(f"Cannot execute statement type: {ast['type']}")

    def explain(self, sql):
        ast = parse(sql)
        plan = make_plan(ast)
        return plan.get('strategy', ast['type'])

    def close(self):
        for table in self.tables.values():
            table.close()


if __name__ == '__main__':
    for f in ('users.db',):
        if os.path.exists(f):
            os.remove(f)

    db = Database()
    db.create_table('users', 'users.db')

    print(db.execute("INSERT INTO users VALUES (1, 'Hamoody')"))
    print(db.execute("INSERT INTO users VALUES (2, 'Balwindar')"))
    print(db.execute("INSERT INTO users VALUES (500, 'Fransis')"))
    print(db.execute("INSERT INTO users VALUES (501, 'Shams')"))

    print()
    print("EXPLAIN SELECT name FROM users WHERE id = 500  ->",
          db.explain("SELECT name FROM users WHERE id = 500"))
    print("EXPLAIN SELECT * FROM users WHERE name = 'Balwindar' ->",
          db.explain("SELECT * FROM users WHERE name = 'Balwindar'"))

    print()
    print("Result (index_lookup path):",
          db.execute("SELECT name FROM users WHERE id = 500"))
    print("Result (full_scan path):   ",
          db.execute("SELECT * FROM users WHERE name = 'Balwindar'"))
    print("Result (no WHERE, * cols): ",
          db.execute("SELECT * FROM users"))

    db.close()
