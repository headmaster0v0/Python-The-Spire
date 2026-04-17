"""Map generation for Slay The Spire - aligned with Java MapGenerator.

Java key components:
- MapGenerator.generateDungeon(): creates nodes and paths
- AbstractDungeon.generateRoomTypes(): creates room list based on percentages
- RoomTypeAssigner.distributeRoomsAcrossMap(): assigns rooms using rules
- RoomTypeAssigner.assignRowAsRoomType(): assigns entire rows

Room type probabilities (Act 1, no ascension):
- shopRoomChance = 0.05 (5%)
- restRoomChance = 0.12 (12%)
- treasureRoomChance = 0.0 (0%)
- eliteRoomChance = 0.08 (8%)
- eventRoomChance = 0.22 (22%)
- monsterRoomChance = 53% (rest)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import random

from sts_py.engine.core.rng import MutableRNG


@dataclass
class MapEdge:
    src_x: int
    src_y: int
    dst_x: int
    dst_y: int

    def __lt__(self, other: "MapEdge") -> bool:
        return self.dst_x < other.dst_x


@dataclass(eq=False)
class MapRoomNode:
    x: int
    y: int
    edges: list[MapEdge] = field(default_factory=list)
    parents: list["MapRoomNode"] = field(default_factory=list)
    room_type: str = "M"

    def add_edge(self, edge: MapEdge) -> None:
        # Avoid duplicate edges
        for existing in self.edges:
            if existing.dst_x == edge.dst_x and existing.dst_y == edge.dst_y:
                return
        self.edges.append(edge)
        self.edges.sort()

    def has_edges(self) -> bool:
        return len(self.edges) > 0

    def get_parents(self) -> list["MapRoomNode"]:
        return self.parents

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "edges": [
                {"src_x": e.src_x, "src_y": e.src_y, "dst_x": e.dst_x, "dst_y": e.dst_y}
                for e in self.edges
            ],
            "room_type": self.room_type,
        }


def create_nodes(height: int, width: int) -> list[list[MapRoomNode]]:
    nodes = []
    for y in range(height):
        row = []
        for x in range(width):
            row.append(MapRoomNode(x=x, y=y))
        nodes.append(row)
    return nodes


def get_node(x: int, y: int, nodes: list[list[MapRoomNode]]) -> MapRoomNode:
    return nodes[y][x]


def get_max_edge(edges: list[MapEdge]) -> MapEdge:
    return max(edges, key=lambda e: e.dst_x)


def get_min_edge(edges: list[MapEdge]) -> MapEdge:
    return min(edges, key=lambda e: e.dst_x)


def get_node_with_max_x(nodes: list[MapRoomNode]) -> MapRoomNode:
    return max(nodes, key=lambda n: n.x)


def get_node_with_min_x(nodes: list[MapRoomNode]) -> MapRoomNode:
    return min(nodes, key=lambda n: n.x)


def get_common_ancestor(
    node1: MapRoomNode,
    node2: MapRoomNode,
    max_depth: int
) -> MapRoomNode | None:
    # Determine left and right nodes for ancestor search
    if node1.x < node2.x:
        l_node, r_node = node1, node2
    else:
        l_node, r_node = node2, node1

    # Java: for (int current_y = node1.y; current_y >= 0 && current_y >= node1.y - max_depth; --current_y)
    # This means: current_y from node1.y down to node1.y - max_depth (inclusive)
    for current_y in range(node1.y, node1.y - max_depth - 1, -1):
        if current_y < 0:
            break
        if not l_node.get_parents() or not r_node.get_parents():
            return None

        l_node = get_node_with_max_x(l_node.get_parents())
        r_node = get_node_with_min_x(r_node.get_parents())

        if l_node is r_node:
            return l_node

    return None


def rand_range(rng: MutableRNG, min_val: int, max_val: int) -> int:
    # Java: rng.random(max - min) + min where rng.random(n) = nextInt(n) = [0, n)
    result = rng.random_int(max_val - min_val) + min_val
    # Defensive bounds check - should never happen if RNG is correct
    if result < min_val or result > max_val:
        raise ValueError(f"rand_range({min_val}, {max_val}) returned {result}")
    return result


def _create_paths(
    nodes: list[list[MapRoomNode]],
    edge: MapEdge,
    rng: MutableRNG
) -> list[list[MapRoomNode]]:
    current_node = get_node(edge.dst_x, edge.dst_y, nodes)

    if edge.dst_y + 1 >= len(nodes):
        new_edge = MapEdge(edge.dst_x, edge.dst_y, 3, edge.dst_y + 2)
        current_node.add_edge(new_edge)
        return nodes

    row_width = len(nodes[edge.dst_y])
    row_end_node = row_width - 1

    if edge.dst_x == 0:
        min_val, max_val = 0, 1
    elif edge.dst_x == row_end_node:
        min_val, max_val = -1, 0
    else:
        min_val, max_val = -1, 1

    new_edge_x = edge.dst_x + rand_range(rng, min_val, max_val)
    new_edge_y = edge.dst_y + 1

    target_node_candidate = get_node(new_edge_x, new_edge_y, nodes)

    min_ancestor_gap = 3
    max_ancestor_gap = 5

    parents = target_node_candidate.get_parents()
    if parents:
        for parent in parents:
            if parent is current_node:
                continue
            ancestor = get_common_ancestor(parent, current_node, max_ancestor_gap)
            if ancestor is None:
                continue

            ancestor_gap = new_edge_y - ancestor.y
            if ancestor_gap < min_ancestor_gap:
                if target_node_candidate.x > current_node.x:
                    new_edge_x = edge.dst_x + rand_range(rng, -1, 0)
                    if new_edge_x < 0:
                        new_edge_x = edge.dst_x
                elif target_node_candidate.x == current_node.x:
                    new_edge_x = edge.dst_x + rand_range(rng, -1, 1)
                    if new_edge_x > row_end_node:
                        new_edge_x = edge.dst_x - 1
                    elif new_edge_x < 0:
                        new_edge_x = edge.dst_x + 1
                else:
                    new_edge_x = edge.dst_x + rand_range(rng, 0, 1)
                    if new_edge_x > row_end_node:
                        new_edge_x = edge.dst_x
                target_node_candidate = get_node(new_edge_x, new_edge_y, nodes)
                continue  # Java: continue to next parent
            if ancestor_gap < max_ancestor_gap:
                continue  # Java: continue to next parent

    if edge.dst_x != 0:
        left_node = nodes[edge.dst_y][edge.dst_x - 1]
        if left_node.has_edges():
            right_edge_of_left = get_max_edge(left_node.edges)
            if right_edge_of_left.dst_x > new_edge_x:
                new_edge_x = right_edge_of_left.dst_x

    if edge.dst_x < row_end_node:
        right_node = nodes[edge.dst_y][edge.dst_x + 1]
        if right_node.has_edges():
            left_edge_of_right = get_min_edge(right_node.edges)
            if left_edge_of_right.dst_x < new_edge_x:
                new_edge_x = left_edge_of_right.dst_x

    target_node_candidate = get_node(new_edge_x, new_edge_y, nodes)

    new_edge = MapEdge(edge.dst_x, edge.dst_y, new_edge_x, new_edge_y)
    current_node.add_edge(new_edge)
    target_node_candidate.parents.append(current_node)
    return _create_paths(nodes, new_edge, rng)


def create_paths(
    nodes: list[list[MapRoomNode]],
    path_density: int,
    rng: MutableRNG
) -> list[list[MapRoomNode]]:
    first_row = 0
    row_size = len(nodes[first_row]) - 1
    first_starting_node = -1

    for i in range(path_density):
        starting_node = rand_range(rng, 0, row_size)
        if i == 0:
            first_starting_node = starting_node
        while starting_node == first_starting_node and i == 1:
            starting_node = rand_range(rng, 0, row_size)

        _create_paths(nodes, MapEdge(starting_node, -1, starting_node, 0), rng)

    return nodes


def filter_redundant_edges(nodes: list[list[MapRoomNode]]) -> list[list[MapRoomNode]]:
    existing_edges: list[MapEdge] = []
    for node in nodes[0]:
        if not node.has_edges():
            continue
        to_remove: list[MapEdge] = []
        for edge in node.edges:
            for prev_edge in existing_edges:
                if edge.dst_x == prev_edge.dst_x and edge.dst_y == prev_edge.dst_y:
                    to_remove.append(edge)
            existing_edges.append(edge)
        for edge in to_remove:
            if edge in node.edges:
                node.edges.remove(edge)
    return nodes


def generate_dungeon(
    height: int,
    width: int,
    path_density: int,
    rng: MutableRNG
) -> list[list[MapRoomNode]]:
    nodes = create_nodes(height, width)
    nodes = create_paths(nodes, path_density, rng)
    nodes = filter_redundant_edges(nodes)
    return nodes


def get_connected_node_count(nodes: list[list[MapRoomNode]]) -> int:
    count = 0
    for row in nodes:
        for node in row:
            if node.has_edges() and node.y != len(nodes) - 2:
                count += 1
    return count


def get_siblings(
    nodes: list[list[MapRoomNode]],
    parents: list[MapRoomNode],
    n: MapRoomNode
) -> list[MapRoomNode]:
    siblings = []
    for parent in parents:
        for edge in parent.edges:
            sibling_node = get_node(edge.dst_x, edge.dst_y, nodes)
            if sibling_node != n:
                siblings.append(sibling_node)
    return siblings


def rule_sibling_matches(siblings: list[MapRoomNode], room_type: str) -> bool:
    applicable_rooms = {"R", "M", "?", "E", "$", "B"}
    if room_type not in applicable_rooms:
        return False
    for sibling_node in siblings:
        if sibling_node.room_type == room_type:
            return True
    return False


def rule_parent_matches(parents: list[MapRoomNode], room_type: str) -> bool:
    applicable_rooms = {"R", "T", "$", "E", "B"}
    if room_type not in applicable_rooms:
        return False
    for parent_node in parents:
        if parent_node.room_type == room_type:
            return True
    return False


def rule_assignable_to_row(n: MapRoomNode, room_type: str) -> bool:
    applicable_rooms_restrict = {"R", "E", "B"}
    if n.y <= 4 and room_type in applicable_rooms_restrict:
        return False
    if n.y >= 13 and room_type == "R":
        return False
    if n.y >= 12 and room_type == "B":
        return False
    return True


def get_next_room_type_according_to_rules(
    nodes: list[list[MapRoomNode]],
    n: MapRoomNode,
    room_list: list[str]
) -> str | None:
    parents = n.get_parents()
    siblings = get_siblings(nodes, parents, n)

    for room_to_be_set in room_list:
        if not rule_assignable_to_row(n, room_to_be_set):
            continue
        if not rule_parent_matches(parents, room_to_be_set) and not rule_sibling_matches(siblings, room_to_be_set):
            return room_to_be_set
        if n.y == 0:
            return room_to_be_set
    return None


def assign_rooms_to_nodes(
    nodes: list[list[MapRoomNode]],
    room_list: list[str]
) -> None:
    for row in nodes:
        for node in row:
            if node is None or not node.has_edges() or node.room_type != "M":
                continue
            if node.y == 0:
                continue
            room_to_be_set = get_next_room_type_according_to_rules(nodes, node, room_list)
            if room_to_be_set is not None:
                room_list.remove(room_to_be_set)
                node.room_type = room_to_be_set


def shuffle_with_rng(rng: MutableRNG, room_list: list[str]) -> list[str]:
    # Java Collections.shuffle uses Random.nextInt(i) which returns [0, i)
    # MutableRNGJavaWrapper.next_int(n) returns [0, n)
    n = len(room_list)
    for i in range(n, 1, -1):
        j = rng.next_int(i)
        room_list[i - 1], room_list[j] = room_list[j], room_list[i - 1]
    return room_list


def distribute_rooms_across_map(
    rng: MutableRNG,
    nodes: list[list[MapRoomNode]],
    room_list: list[str]
) -> list[list[MapRoomNode]]:
    node_count = get_connected_node_count(nodes)

    while len(room_list) < node_count:
        room_list.append("M")

    if len(room_list) > node_count:
        pass

    shuffle_with_rng(rng, room_list)
    assign_rooms_to_nodes(nodes, room_list)

    for row in nodes:
        for node in row:
            if node is None or not node.has_edges() or node.room_type != "M":
                continue
            node.room_type = "M"

    return nodes


def assign_row_as_room_type(
    nodes: list[list[MapRoomNode]],
    row_index: int,
    room_type: str
) -> None:
    if row_index >= len(nodes):
        return
    for node in nodes[row_index]:
        if node is None or not node.has_edges():
            continue
        node.room_type = room_type


def generate_room_types(
    available_room_count: int,
    shop_room_chance: float = 0.05,
    rest_room_chance: float = 0.12,
    treasure_room_chance: float = 0.0,
    elite_room_chance: float = 0.08,
    event_room_chance: float = 0.22,
    boss_room_chance: float = 0.0
) -> list[str]:
    room_list: list[str] = []

    shop_count = round(available_room_count * shop_room_chance)
    rest_count = round(available_room_count * rest_room_chance)
    treasure_count = round(available_room_count * treasure_room_chance)
    elite_count = round(available_room_count * elite_room_chance)
    event_count = round(available_room_count * event_room_chance)
    boss_count = round(available_room_count * boss_room_chance)

    for _ in range(shop_count):
        room_list.append("$")
    for _ in range(rest_count):
        room_list.append("R")
    for _ in range(elite_count):
        room_list.append("E")
    for _ in range(event_count):
        room_list.append("?")
    for _ in range(treasure_count):
        room_list.append("T")
    for _ in range(boss_count):
        room_list.append("B")

    return room_list


def generate_map(
    height: int = 15,
    width: int = 7,
    path_density: int = 6,
    rng: MutableRNG | None = None,
    act: int = 1,
    shop_room_chance: float = 0.05,
    rest_room_chance: float = 0.12,
    treasure_room_chance: float = 0.0,
    elite_room_chance: float = 0.08,
    event_room_chance: float = 0.22,
    boss_room_chance: float = 0.0
) -> list[list[MapRoomNode]]:
    if rng is None:
        rng = MutableRNG.from_seed(0, rng_type="map")

    nodes = generate_dungeon(height, width, path_density, rng)

    node_count = get_connected_node_count(nodes)
    room_list = generate_room_types(
        node_count,
        shop_room_chance,
        rest_room_chance,
        treasure_room_chance,
        elite_room_chance,
        event_room_chance,
        boss_room_chance
    )

    assign_row_as_room_type(nodes, height - 2, "R")
    assign_row_as_room_type(nodes, height - 1, "B")
    assign_row_as_room_type(nodes, 0, "M")
    if height > 8:
        assign_row_as_room_type(nodes, 8, "T")

    nodes = distribute_rooms_across_map(rng, nodes, room_list)

    return nodes


def map_to_string(nodes: list[list[MapRoomNode]], show_symbols: bool = True) -> str:
    lines = []

    for row_num in range(len(nodes) - 1, -1, -1):
        row = nodes[row_num]

        edge_line = "     "
        for node in row:
            left, mid, right = " ", " ", " "
            for edge in node.edges:
                if edge.dst_x < node.x:
                    left = "\\"
                if edge.dst_x == node.x:
                    mid = "|"
                if edge.dst_x > node.x:
                    right = "/"
            edge_line += left + mid + right
        lines.append(edge_line)

        node_line = f"{row_num}  "
        for node in row:
            symbol = " "
            if row_num == len(nodes) - 1:
                for lower_node in nodes[row_num - 1]:
                    for edge in lower_node.edges:
                        if edge.dst_x == node.x:
                            symbol = node.room_type if show_symbols else "*"
            elif node.has_edges():
                symbol = node.room_type if show_symbols else "*"
            node_line += " " + symbol + " "
        lines.append(node_line)

    return "\n".join(lines)
