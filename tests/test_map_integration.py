from __future__ import annotations

from play_cli import format_map_lines
from sts_py.engine.run.run_engine import RunEngine


SEED_STRING = "1B40C4J3IIYDA"


class TestMapIntegration:
    def test_generated_map_nodes_are_non_empty(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        assert len(engine.state.map_nodes) > 0

    def test_connection_indices_are_valid(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        node_count = len(engine.state.map_nodes)
        for node in engine.state.map_nodes:
            for connection in node.connections:
                assert 0 <= connection < node_count

    def test_initial_paths_are_start_nodes(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        paths = engine.get_available_paths()
        assert len(paths) >= 1
        assert all(not node.parent_indices for node in paths)
        assert all(node.floor == 1 for node in paths)

    def test_next_paths_follow_selected_node_connections(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        first = engine.get_available_paths()[0]
        assert engine.choose_path(first.node_id)

        expected_ids = sorted(first.connections)
        actual_ids = sorted(node.node_id for node in engine.get_available_paths())
        assert actual_ids == expected_ids

    def test_choose_invalid_non_connected_node_fails(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        first = engine.get_available_paths()[0]
        assert engine.choose_path(first.node_id)

        valid_ids = {node.node_id for node in engine.get_available_paths()}
        invalid_node = next(
            node
            for node in engine.state.map_nodes
            if node.node_id not in valid_ids and node.node_id != first.node_id
        )
        assert engine.choose_path(invalid_node.node_id) is False

    def test_format_map_lines_marks_available_start_nodes(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)

        lines = format_map_lines(engine)

        assert any(line.startswith("  首领:") for line in lines)
        assert any("[" in line and "]" in line for line in lines)
        assert any(any(glyph in line for glyph in ("/", "|", "\\")) for line in lines)

    def test_format_map_lines_marks_current_and_next_paths(self):
        engine = RunEngine.create(SEED_STRING, ascension=0)
        first = engine.get_available_paths()[0]
        assert engine.choose_path(first.node_id)

        lines = format_map_lines(engine)

        assert any("<" in line and ">" in line for line in lines)
        assert sum(line.count("<") for line in lines) == 1
        assert any(line.startswith("  F01:") and "[" in line and "]" in line for line in lines)
