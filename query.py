"""
Execution uses Python generators as the iterator model: each operator
pulls one row at a time from the operator below it.
"""

import re

TOKEN_REGEX = re.compile(r"'[^']*'|[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[=<>!]+|\*|,|\(|\)")


def tokenize(sql):
    return TOKEN_REGEX.findall(sql)

def parse(sql):
    tokens = tokenize(sql)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def advance():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_literal(tok):
        if tok.startswith("'"):
            return tok[1:-1]
        return int(tok)

    keyword = advance().upper()

    if keyword == 'SELECT':
        columns = []
        tok = advance()
        columns.append(tok)
        while peek() == ',':
            advance()
            columns.append(advance())

        if advance().upper() != 'FROM':
            raise ValueError("Expected FROM")
        table = advance()

        where = None
        if peek() and peek().upper() == 'WHERE':
            advance()
            column = advance()
            op = advance()
            value = parse_literal(advance())
            where = {'column': column, 'op': op, 'value': value}

        return {'type': 'select', 'columns': columns, 'table': table, 'where': where}

    elif keyword == 'INSERT':
        if advance().upper() != 'INTO':
            raise ValueError("Expected INTO")
        table = advance()
        if advance().upper() != 'VALUES':
            raise ValueError("Expected VALUES")
        if advance() != '(':
            raise ValueError("Expected (")

        values = []
        while peek() != ')':
            tok = advance()
            if tok == ',':
                continue
            values.append(parse_literal(tok))
        advance()  # consume ')'

        return {'type': 'insert', 'table': table, 'values': values}

    else:
        raise ValueError(f"Unsupported statement: {keyword}")


def make_plan(ast):
    """Decide index_lookup vs full_scan for SELECTs. Returns ast + 'strategy'."""
    if ast['type'] != 'select':
        return ast

    where = ast['where']
    if where is not None and where['column'] == 'id' and where['op'] == '=':
        strategy = 'index_lookup'
    else:
        strategy = 'full_scan'

    return {**ast, 'strategy': strategy}

def scan_op(table):
    """Full table scan, O(n): reads every row via the storage layer."""
    yield from table.full_scan()


def index_scan_op(table, key):
    """Index lookup, O(log n): one B+ tree search, at most one row out."""
    row = table.index_lookup(key)
    if row is not None:
        yield row


def filter_op(rows, where):
    """Pulls from `rows` one at a time, only re-yielding matches."""
    if where is None:
        yield from rows
        return

    column, op, value = where['column'], where['op'], where['value']
    for row in rows:
        row_value = row[column]
        if op == '=' and row_value == value:
            yield row
        elif op == '!=' and row_value != value:
            yield row
        elif op == '<' and row_value < value:
            yield row
        elif op == '>' and row_value > value:
            yield row


def project_op(rows, columns):
    """Strips each row down to just the requested columns."""
    for row in rows:
        if columns == ['*']:
            yield row
        else:
            yield {c: row[c] for c in columns}


def execute_select(plan, table):
    if plan['strategy'] == 'index_lookup':
        rows = index_scan_op(table, plan['where']['value'])
    else:
        rows = scan_op(table)
        rows = filter_op(rows, plan['where'])

    rows = project_op(rows, plan['columns'])
    return list(rows)
