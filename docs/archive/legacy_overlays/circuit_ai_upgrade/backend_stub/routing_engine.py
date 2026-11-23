"""
Circuit-AI Routing Engine
=========================
"Devouring" the capabilities of Freerouting.
Implements a grid-based A* pathfinding algorithm to route PCB traces autonomously.
"""

import heapq
import math
from typing import List, Tuple, Set, Dict, Optional

class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __lt__(self, other):
        return (self.x, self.y) < (other.x, other.y)
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __repr__(self):
        return f"({self.x}, {self.y})"

class AutoRouter:
    def __init__(self, width: int, height: int, resolution: float = 0.5):
        self.width = width
        self.height = height
        self.resolution = resolution
        self.grid_w = int(width / resolution)
        self.grid_h = int(height / resolution)
        self.obstacles: Set[Point] = set()

    def _to_grid(self, x: float, y: float) -> Point:
        return Point(int(x / self.resolution), int(y / self.resolution))

    def _to_world(self, p: Point) -> Tuple[float, float]:
        return (p.x * self.resolution, p.y * self.resolution)

    def add_obstacle(self, x: float, y: float, w: float, h: float):
        """Mark an area (like a chip) as untraversable"""
        gp = self._to_grid(x, y)
        gw = int(w / self.resolution)
        gh = int(h / self.resolution)
        for i in range(gw):
            for j in range(gh):
                self.obstacles.add(Point(gp.x + i, gp.y + j))

    def route_net(self, start: Tuple[float, float], end: Tuple[float, float]) -> Optional[List[Tuple[float, float]]]:
        """A* Pathfinding to connect two points"""
        start_node = self._to_grid(*start)
        end_node = self._to_grid(*end)
        
        open_set = []
        heapq.heappush(open_set, (0, start_node))
        
        came_from: Dict[Point, Point] = {}
        g_score: Dict[Point, float] = {start_node: 0}
        f_score: Dict[Point, float] = {start_node: self._heuristic(start_node, end_node)}
        
        while open_set:
            current = heapq.heappop(open_set)[1]
            
            if current == end_node:
                return self._reconstruct_path(came_from, current)
            
            for neighbor in self._get_neighbors(current):
                if neighbor in self.obstacles and neighbor != end_node and neighbor != start_node:
                    continue
                
                tentative_g = g_score[current] + 1 # Cost is 1 per step
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._heuristic(neighbor, end_node)
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, neighbor))
                    
        return None # No path found

    def _heuristic(self, a: Point, b: Point) -> float:
        # Manhattan distance is good for PCBs (Manhattan routing)
        return abs(a.x - b.x) + abs(a.y - b.y)

    def _get_neighbors(self, p: Point) -> List[Point]:
        neighbors = []
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]: # 4-connectivity (90 degree turns)
            nx, ny = p.x + dx, p.y + dy
            if 0 <= nx < self.grid_w and 0 <= ny < self.grid_h:
                neighbors.append(Point(nx, ny))
        return neighbors

    def _reconstruct_path(self, came_from: Dict[Point, Point], current: Point) -> List[Tuple[float, float]]:
        total_path = [self._to_world(current)]
        while current in came_from:
            current = came_from[current]
            total_path.append(self._to_world(current))
        return total_path[::-1]

if __name__ == "__main__":
    # DEMO
    router = AutoRouter(80, 60, resolution=1.0)
    # Add a "Chip" obstacle in the middle
    router.add_obstacle(35, 25, 10, 10) 
    
    print("Routing from (10,10) to (60,40)...")
    path = router.route_net((10, 10), (60, 40))
    
    if path:
        print(f"Path Found! Length: {len(path)} segments")
        print(f"Start: {path[0]}")
        print(f"Mid:   {path[len(path)//2]}")
        print(f"End:   {path[-1]}")
    else:
        print("Failed to route.")
