"""Behavioral tests for the bounded workflow-output discovery walker."""

from __future__ import annotations

from pathlib import Path

from insar_pilot.services.output_discovery import OutputDiscoveryService


def test_discover_only_returns_known_roots(tmp_path: Path):
    (tmp_path / "run_files").mkdir()
    (tmp_path / "merged").mkdir()
    (tmp_path / "unrelated").mkdir()  # not in ROOTS -> ignored

    nodes = OutputDiscoveryService().discover(tmp_path)

    names = {node.name for node in nodes}
    assert names == {"run_files", "merged"}
    assert all(node.kind == "directory" for node in nodes)


def test_discover_builds_nested_tree_with_file_and_directory_kinds(tmp_path: Path):
    root = tmp_path / "configs"
    (root / "sub").mkdir(parents=True)
    (root / "config_a").write_text("a", encoding="utf-8")
    (root / "sub" / "leaf").write_text("l", encoding="utf-8")

    nodes = OutputDiscoveryService().discover(tmp_path)

    configs = next(node for node in nodes if node.name == "configs")
    child_names = {child.name for child in configs.children}
    assert child_names == {"sub", "config_a"}
    file_child = next(child for child in configs.children if child.name == "config_a")
    dir_child = next(child for child in configs.children if child.name == "sub")
    assert file_child.kind == "file"
    assert dir_child.kind == "directory"
    assert [c.name for c in dir_child.children] == ["leaf"]


def test_discover_respects_max_depth(tmp_path: Path):
    deep = tmp_path / "merged" / "level1" / "level2"
    deep.mkdir(parents=True)
    (deep / "deep_file").write_text("x", encoding="utf-8")

    nodes = OutputDiscoveryService().discover(tmp_path, max_depth=1)

    merged = nodes[0]
    level1 = merged.children[0]
    assert level1.name == "level1"
    # Depth capped: level1's children are not expanded.
    assert level1.children == []


def test_discover_truncates_when_over_max_children(tmp_path: Path):
    root = tmp_path / "merged"
    root.mkdir()
    for i in range(5):
        (root / f"item_{i}").write_text("x", encoding="utf-8")

    nodes = OutputDiscoveryService().discover(tmp_path, max_children=2)

    merged = nodes[0]
    assert len(merged.children) == 3  # 2 visible + 1 truncation marker
    marker = merged.children[-1]
    assert marker.kind == "truncated"
    assert "3 more items" in marker.name
