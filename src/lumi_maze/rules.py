"""Pure game rules for a single run: state, timer, movement, scoring."""
from dataclasses import dataclass, field
from typing import Literal, Set

from lumi_maze.core import Maze, Cell


@dataclass
class RunState:
    """Mutable state of one playthrough.

    Attributes:
        maze: Level definition (immutable).
        mode: 'timed' — timer can end the run; 'easy' — no timeout, fruit gives points.
        cell: Current player cell.
        status: 'playing' | 'won' | 'lost'.
        time_left: Seconds remaining (timed mode only).
        freeze_left: Seconds of timer freeze remaining.
        speed_factor: Timer speed multiplier (strawberry effect).
        steps: Number of successful moves made.
        collected: Cells whose items have been picked up.
        level_points: Final score for this level (route + fruit).
        fruit_points: Points from fruits (easy mode only).
    """
    maze: Maze
    mode: Literal['timed', 'easy']
    cell: Cell = field(init=False)
    status: Literal['playing', 'won', 'lost'] = field(init=False, default='playing')
    time_left: float = field(init=False)
    freeze_left: float = field(init=False, default=0.0)
    speed_factor: float = field(init=False, default=1.0)
    steps: int = field(init=False, default=0)
    collected: Set[Cell] = field(init=False, default_factory=set)
    level_points: int = field(init=False, default=0)
    fruit_points: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.mode not in ('timed', 'easy'):
            raise ValueError(f"mode must be 'timed' or 'easy', got {self.mode!r}")
        self.cell = self.maze.start
        self.time_left = float(self.maze.time_limit)

    def tick(self, dt: float) -> None:
        """Advance the timer by dt seconds.

        Args:
            dt: Non-negative delta time.

        Behavior:
            - If dt < 0: raise ValueError.
            - If status != 'playing' or mode == 'easy': return (timer paused or disabled).
            - Consume min(dt, freeze_left) from freeze_left.
            - Decrement time_left by remaining_dt * speed_factor.
            - Clamp time_left to >= 0; if it reaches 0, set status = 'lost'.
        """
        if dt < 0:
            raise ValueError("dt must be non-negative")

        if self.status != 'playing' or self.mode == 'easy':
            return

        # Consume freeze first
        freeze_used = min(dt, self.freeze_left)
        self.freeze_left -= freeze_used
        remaining_dt = dt - freeze_used

        if remaining_dt > 0:
            self.time_left = max(0.0, self.time_left - remaining_dt * self.speed_factor)
            if self.time_left <= 0:
                self.time_left = 0.0
                self.status = 'lost'

    def try_move(self, target: Cell) -> str | None:
        """Attempt to move to an adjacent open cell.

        Args:
            target: Destination cell.

        Returns:
            Name of collected item ('apple', 'strawberry', 'trampoline') if an
            uncollected item was on the target cell, otherwise None.

        State changes only on success (open neighbor, playing status).
        On success: increments steps, updates cell, collects item if any.
        If target is the exit: sets status='won' and computes level_points.
        """
        if self.status != 'playing':
            return None
        if not self.maze.is_open(self.cell, target):
            return None

        # Valid move
        self.steps += 1
        self.cell = target

        collected_item = None
        if target in self.maze.items and target not in self.collected:
            item = self.maze.items[target]
            self.collected.add(target)
            collected_item = item

            if item == 'apple':
                if self.mode == 'timed':
                    self.freeze_left += 10.0
                else:  # easy
                    self.fruit_points += 150
            elif item == 'strawberry':
                if self.mode == 'timed':
                    self.speed_factor *= 0.5
                else:  # easy
                    self.fruit_points += 150
            elif item == 'trampoline':
                # No numeric effect, just event
                pass

        # Check for win
        if self.cell == self.maze.exit:
            self.status = 'won'
            optimum = len(self.maze.shortest_path()) - 1
            route_points = round(1000 * optimum / max(optimum, self.steps))
            self.level_points = route_points + self.fruit_points

        return collected_item