from lumi_maze.core import Maze, generate_level

def test_core_basic():
    maze = generate_level(1, 42)
    assert maze.width == 7
    assert maze.height == 7
    assert maze.start == (0, 0)
    assert maze.exit == (6, 6)
    assert len(maze.passages) == maze.width * maze.height - 1
    assert maze.theme == "stone"
    assert len(maze.items) == 3
    for cell, itype in maze.items.items():
        assert cell != maze.start
        assert cell != maze.exit
        assert itype in ("apple", "strawberry", "trampoline")

def test_is_open_and_neighbors():
    maze = generate_level(1, 123)
    # Test valid neighbors and is_open symmetry
    for cell in maze.passages:
        a, b = cell
        assert maze.is_open(a, b)
        assert maze.is_open(b, a)
        assert b in maze.neighbors(a)
        assert a in maze.neighbors(b)

    # Out of bounds or walls
    assert not maze.is_open((-1, 0), (0, 0))
    assert not maze.is_open((0, 0), (10, 10))
    assert not maze.is_open((0, 0), (0, 2))  # not adjacent

def test_shortest_path():
    maze = generate_level(1, 99)
    path = maze.shortest_path()
    assert path[0] == maze.start
    assert path[-1] == maze.exit
    for i in range(len(path) - 1):
        assert maze.is_open(path[i], path[i+1])

def test_multiple_levels_and_seeds():
    for level in range(1, 6):
        m1 = generate_level(level, 100)
        m2 = generate_level(level, 100)
        m3 = generate_level(level, 200)

        # Determinism
        assert m1.width == m2.width
        assert m1.passages == m2.passages
        assert m1.items == m2.items
        assert m1.time_limit == m2.time_limit

        # Different seed
        assert m1.passages != m3.passages or m1.items != m3.items

        # Dimensions grow
        expected_w = min(7 + 2 * (level - 1), 19)
        assert m1.width == expected_w
        assert m1.height == expected_w
        assert len(m1.passages) == expected_w * expected_w - 1

        # All 3 items present
        types = list(m1.items.values())
        assert sorted(types) == ["apple", "strawberry", "trampoline"]

def test_themes():
    themes = ["stone", "forest", "cave", "streams"]
    for i, theme in enumerate(themes, 1):
        m = generate_level(i, 555)
        assert m.theme == theme

def test_all_cells_reachable():
    for level in range(1, 8):
        maze = generate_level(level, 42)
        visited = set()
        queue = [maze.start]
        visited.add(maze.start)

        while queue:
            cell = queue.pop()
            for neighbor in maze.neighbors(cell):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # All cells should be reachable
        assert len(visited) == maze.width * maze.height


def test_items_collectible_before_exit():
    # Test seeds: 20261019, 0, 1, 42
    seeds = [20261019, 0, 1, 42]
    for level in range(1, 8):
        for seed in seeds:
            maze = generate_level(level, seed)
            visited = set()
            queue = [maze.start]
            visited.add(maze.start)

            # Collect all items without visiting exit
            while queue:
                cell = queue.pop()
                for neighbor in maze.neighbors(cell):
                    if neighbor == maze.exit:
                        continue  # Skip exit
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            # Check that all items are in visited cells (not on start or exit)
            for cell, _ in maze.items.items():
                assert cell != maze.start, f"Item on start for level {level}, seed {seed}"
                assert cell != maze.exit, f"Item on exit for level {level}, seed {seed}"
                assert cell in visited, f"Item at {cell} not reachable without visiting exit for level {level}, seed {seed}"

            # Ensure all 3 items are reachable
            assert len(maze.items) == 3, f"Expected 3 items for level {level}, seed {seed}"

def test_time_limit_growth():
    seed = 100
    for level in range(1, 8):
        maze = generate_level(level, seed)
        if level > 1:
            prev_maze = generate_level(level - 1, seed)
            assert maze.time_limit >= prev_maze.time_limit + 15

def test_time_limit_formula():
    for level in range(1, 8):
        maze = generate_level(level, 42)
        optimum = len(maze.shortest_path()) - 1
        base_time = 80.0 + 15.0 * (level - 1)
        optimum_time = optimum * 3.0 + 35.0
        assert maze.time_limit >= max(base_time, optimum_time)

def test_level_range_validation():
    for level in [0, 8, -1, 9]:
        try:
            generate_level(level, 42)
            assert False, "generate_level should raise ValueError for invalid levels"
        except ValueError:
            pass