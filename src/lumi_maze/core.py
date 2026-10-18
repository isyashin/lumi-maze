import random
from dataclasses import dataclass
from typing import Literal

Cell = tuple[int, int]

@dataclass(frozen=True)
class Maze:
    width: int
    height: int
    passages: frozenset[tuple[Cell, Cell]]
    start: Cell
    exit: Cell
    items: dict[Cell, str]
    theme: str
    time_limit: float

    def is_open(self, a: Cell, b: Cell) -> bool:
        if not (0 <= a[0] < self.width and 0 <= a[1] < self.height):
            return False
        if not (0 <= b[0] < self.width and 0 <= b[1] < self.height):
            return False
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            return False
        return (a, b) in self.passages or (b, a) in self.passages

    def neighbors(self, cell: Cell) -> tuple[Cell, ...]:
        x, z = cell
        candidates = [(x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)]
        valid = [c for c in candidates if 0 <= c[0] < self.width and 0 <= c[1] < self.height and self.is_open(cell, c)]
        return tuple(valid)

    def shortest_path(self) -> list[Cell]:
        from collections import deque
        queue = deque([[self.start]])
        visited = {self.start}
        while queue:
            path = queue.popleft()
            curr = path[-1]
            if curr == self.exit:
                return path
            for nxt in self.neighbors(curr):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(path + [nxt])
        raise RuntimeError("No path found from start to exit")

def generate_level(level: int, seed: int) -> Maze:
    # Validate level range
    if not 1 <= level <= 7:
        raise ValueError("Level must be between 1 and 7")
    # Dimensions: 7x7 on level 1, +2 per level up to 19x19
    width = min(7 + 2 * (level - 1), 19)
    height = width

    # RNG with stable seed + level offset
    rng = random.Random(seed + level * 1000 + 7)

    # DFS Perfect Maze generation
    # Cells represented as (x, z) where 0 <= x < width, 0 <= z < height
    passages_set = set()
    visited_cells = set()
    stack = []

    start_cell = (0, 0)
    visited_cells.add(start_cell)
    stack.append(start_cell)

    while stack:
        curr = stack[-1]
        cx, cz = curr
        # Get unvisited neighbors (step size 1)
        neighbors = []
        for nx, nz in [(cx+1, cz), (cx-1, cz), (cx, cz+1), (cx, cz-1)]:
            if 0 <= nx < width and 0 <= nz < height and (nx, nz) not in visited_cells:
                neighbors.append((nx, nz))
        
        if neighbors:
            rng.shuffle(neighbors)
            nxt = neighbors[0]
            visited_cells.add(nxt)
            passages_set.add((curr, nxt))
            stack.append(nxt)
        else:
            stack.pop()

    passages = frozenset(passages_set)
    start = (0, 0)
    exit_cell = (width - 1, height - 1)

    # Themes: stone, forest, cave, streams by loop
    themes = ["stone", "forest", "cave", "streams"]
    theme = themes[(level - 1) % len(themes)]

    # Temporary Maze object to compute shortest path and optimum
    # We construct with empty items first
    # But wait, we need optimum path to calculate time limit.
    # Let's create a temporary helper or evaluate shortest path using passages.
    
    # Use a temporary Maze instance to compute the shortest path
    temp_maze = Maze(
        width=width,
        height=height,
        passages=passages,
        start=start,
        exit=exit_cell,
        items={},
        theme="dummy",
        time_limit=0.0
    )
    sp = temp_maze.shortest_path()
    optimum = len(sp) - 1



    # Calculate time_limit based on level and optimum path
    base_time = 80.0 + 15.0 * (level - 1)
    optimum_time = optimum * 3.0 + 35.0
    time_limit = max(base_time, optimum_time)
    
    # Ensure time_limit is at least 15 seconds more than the previous level for the same seed
    if level > 1:
        prev_time_limit = generate_level(level - 1, seed).time_limit
        time_limit = max(time_limit, prev_time_limit + 15.0)

    # Items: apple, strawberry, trampoline
    # Ensure distinct cells, not start or exit.
    all_cells = [(x, z) for x in range(width) for z in range(height) if (x, z) != start and (x, z) != exit_cell]
    rng.shuffle(all_cells)

    item_types = ["apple", "strawberry", "trampoline"]
    items = {}
    for itype in item_types:
        if all_cells:
            cell = all_cells.pop()
            items[cell] = itype

    return Maze(
        width=width,
        height=height,
        passages=passages,
        start=start,
        exit=exit_cell,
        items=items,
        theme=theme,
        time_limit=time_limit
    )
