"""
B+ tree index

Maps key -> value: 
- Internal nodes hold only keys + child pointers (pure routing, no data).
- Leaf nodes hold the actual (key, value) pairs, kept sorted.
- Leaf nodes are chained left-to-right for fast range scans.
- A node "splits" when it overflows: middle key moves up to the parent.

"""

ORDER = 4  # max children per internal node; max keys per node = ORDER - 1


class Node:
    def __init__(self, leaf=False):
        self.leaf = leaf
        self.keys = []
        self.children = []
        self.next = None 


class BPlusTree:
    def __init__(self, order=ORDER):
        self.order = order
        self.max_keys = order - 1
        self.root = Node(leaf=True)

    def search(self, key):
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                return leaf.children[i]
        return None

    def range_search(self, start, end):
        """Return all (key, value) pairs with start <= key <= end."""
        node = self._find_leaf(start)
        results = []
        while node:
            for i, k in enumerate(node.keys):
                if k > end:
                    return results
                if k >= start:
                    results.append((k, node.children[i]))
            node = node.next 
        return results

    def _find_leaf(self, key):
        node = self.root
        while not node.leaf:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            node = node.children[i]
        return node

    def insert(self, key, value):
        leaf = self._find_leaf(key)
        self._insert_sorted(leaf, key, value)
        if len(leaf.keys) > self.max_keys:
            self._split_leaf(leaf)

    def _insert_sorted(self, node, key, value):
        i = 0
        while i < len(node.keys) and node.keys[i] < key:
            i += 1
        node.keys.insert(i, key)
        node.children.insert(i, value)

    def _split_leaf(self, leaf):
        mid = len(leaf.keys) // 2
        new_leaf = Node(leaf=True)
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.children = leaf.children[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.children = leaf.children[:mid]

        new_leaf.next = leaf.next
        leaf.next = new_leaf

        split_key = new_leaf.keys[0]  
        self._insert_in_parent(leaf, split_key, new_leaf)

    def _split_internal(self, node):
        mid = len(node.keys) // 2
        split_key = node.keys[mid]  

        new_node = Node(leaf=False)
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        self._insert_in_parent(node, split_key, new_node)

    def _insert_in_parent(self, left, key, right):
        if left is self.root:
            new_root = Node(leaf=False)
            new_root.keys = [key]
            new_root.children = [left, right]
            self.root = new_root  
            return

        parent = self._find_parent(self.root, left)
        i = parent.children.index(left)
        parent.keys.insert(i, key)
        parent.children.insert(i + 1, right)

        if len(parent.keys) > self.max_keys:
            self._split_internal(parent)  

    def _find_parent(self, node, child):
        if node.leaf:
            return None
        if child in node.children:
            return node
        for c in node.children:
            found = self._find_parent(c, child)
            if found:
                return found
        return None

    def print_tree(self):
        level = [self.root]
        depth = 0
        while level:
            labels = []
            next_level = []
            for node in level:
                labels.append(str(node.keys))
                if not node.leaf:
                    next_level.extend(node.children)
            print(f"level {depth}: {'  '.join(labels)}")
            level = next_level
            depth += 1


if __name__ == '__main__':
    tree = BPlusTree(order=4)  # max 3 keys per node

    ids = [10, 20, 5, 6, 12, 30, 7, 17, 1, 25, 3, 15]
    for i, key in enumerate(ids):
        tree.insert(key, f"row_index_{i}")

    print("Tree structure after inserts:")
    tree.print_tree()

    print("\nsearch(12):", tree.search(12))
    print("search(999):", tree.search(999))

    print("\nrange_search(6, 17):", tree.range_search(6, 17))

    # Sanity check
    for i, key in enumerate(ids):
        assert tree.search(key) == f"row_index_{i}", f"lost key {key}!"
    print("\nAll inserted keys verified present after splits. ✓")
