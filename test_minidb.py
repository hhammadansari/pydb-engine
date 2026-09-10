"""
Each test uses pytest's tmp_path fixture for an isolated filesystem.
"""

import os
import pytest

from storage import PagedStore, RECORDS_PER_PAGE
from btree import BPlusTree
from table import Table
from engine import Database
from query import parse, make_plan


#storage 
def test_storage_insert_and_get_within_one_page(tmp_path):
    store = PagedStore(str(tmp_path / "data.db"))
    store.insert(1, "Hamoody")
    store.insert(2, "Balwindar")
    store.insert(500, "Fransis")

    assert store.get(0) == {'id': 1, 'name': 'Hamoody'}
    assert store.get(2) == {'id': 500, 'name': 'Fransis'}
    assert store.page_count() == 1
    store.close()


def test_storage_spans_multiple_pages(tmp_path):
    store = PagedStore(str(tmp_path / "data.db"))
    n = RECORDS_PER_PAGE * 2 + 5  #force at least 3 pages
    for i in range(n):
        store.insert(i, f"user{i}")

    assert store.page_count() == 3
    #spot-check across the page boundary
    assert store.get(0) == {'id': 0, 'name': 'user0'}
    assert store.get(RECORDS_PER_PAGE - 1) == {'id': RECORDS_PER_PAGE - 1, 'name': f'user{RECORDS_PER_PAGE - 1}'}
    assert store.get(RECORDS_PER_PAGE) == {'id': RECORDS_PER_PAGE, 'name': f'user{RECORDS_PER_PAGE}'}
    assert store.get(n - 1) == {'id': n - 1, 'name': f'user{n - 1}'}
    store.close()


def test_storage_out_of_range_raises(tmp_path):
    store = PagedStore(str(tmp_path / "data.db"))
    store.insert(1, "Alice")
    with pytest.raises(IndexError):
        store.get(1000)
    store.close()


#B+ tree
def test_btree_insert_and_search_with_many_splits():
    tree = BPlusTree(order=4)  
    keys = list(range(200))
    import random
    random.seed(42)
    random.shuffle(keys)

    for i, k in enumerate(keys):
        tree.insert(k, f"value_{k}")

    for k in keys:
        assert tree.search(k) == f"value_{k}", f"lost key {k} after splits"

    assert tree.search(99999) is None  #missing key


def test_btree_range_search_is_sorted_and_correct():
    tree = BPlusTree(order=4)
    for k in range(100):
        tree.insert(k, f"v{k}")

    result = tree.range_search(20, 30)
    assert [k for k, _ in result] == list(range(20, 31))  #inclusive, in order


#table (storage + index integration)
def test_table_index_rebuilds_correctly_on_reopen(tmp_path):
    data_file = str(tmp_path / "users.db")

    t1 = Table('users', data_file)
    t1.insert(1, "Hamoody")
    t1.insert(500, "Fransis")
    t1.close()

    #Fresh Table object
    t2 = Table('users', data_file)
    assert t2.index_lookup(500) == {'id': 500, 'name': 'Fransis'}
    assert t2.index_lookup(999) is None
    t2.close()


def test_wal_recovers_unapplied_write(tmp_path):
    data_file = str(tmp_path / "users.db")

    t1 = Table('users', data_file)
    t1.insert(1, "Hamoody")

    #Simulate a crash: logged, but never applied to storage/index/checkpoint.
    t1.wal.append(999, "Ghost")

    #"Restart"
    t2 = Table('users', data_file)
    assert t2.index_lookup(999) == {'id': 999, 'name': 'Ghost'}
    t2.close()


#parser
def test_parser_select_with_where():
    ast = parse("SELECT name FROM users WHERE id = 500")
    assert ast == {
        'type': 'select',
        'columns': ['name'],
        'table': 'users',
        'where': {'column': 'id', 'op': '=', 'value': 500},
    }


def test_parser_insert():
    ast = parse("INSERT INTO users VALUES (1, 'Hamoody')")
    assert ast == {'type': 'insert', 'table': 'users', 'values': [1, 'Hamoody']}


def test_planner_picks_index_lookup_for_id_equality():
    ast = parse("SELECT name FROM users WHERE id = 500")
    plan = make_plan(ast)
    assert plan['strategy'] == 'index_lookup'


def test_planner_picks_full_scan_for_non_indexed_column():
    ast = parse("SELECT * FROM users WHERE name = 'Bob'")
    plan = make_plan(ast)
    assert plan['strategy'] == 'full_scan'


#end-to-end engine
def test_engine_end_to_end(tmp_path):
    db = Database()
    db.create_table('users', str(tmp_path / "users.db"))

    db.execute("INSERT INTO users VALUES (1, 'Hamoody')")
    db.execute("INSERT INTO users VALUES (2, 'Balwindar')")
    db.execute("INSERT INTO users VALUES (500, 'Fransis')")

    assert db.execute("SELECT name FROM users WHERE id = 500") == [{'name': 'Fransis'}]
    assert db.execute("SELECT * FROM users WHERE name = 'Bob'") == [{'id': 2, 'name': 'Balwindar'}]
    assert db.execute("SELECT * FROM users WHERE id = 42") == []

    all_rows = db.execute("SELECT * FROM users")
    assert len(all_rows) == 3

    db.close()
