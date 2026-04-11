"""Simple discovery of ISCE native workflow outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class OutputNode:
    name: str
    path: str
    kind: str
    children: list["OutputNode"] = field(default_factory=list)


class OutputDiscoveryService:
    """Walk a bounded subset of the working directory for UI display."""

    ROOTS = (
        "run_files",
        "configs",
        "merged",
        "interferograms",
        "misreg",
        "baselines",
        "geom_reference",
        "reference",
        "secondarys",
        "coreg_secondarys",
        "ion",
        ".iscegui/visualize",
    )

    def discover(self, work_dir: Path, max_depth: int = 3, max_children: int = 50) -> list[OutputNode]:
        nodes: list[OutputNode] = []
        for root_name in self.ROOTS:
            root = work_dir / root_name
            if root.exists():
                nodes.append(self._build_tree(root, depth=0, max_depth=max_depth, max_children=max_children))
        return nodes

    def _build_tree(self, path: Path, depth: int, max_depth: int, max_children: int) -> OutputNode:
        node = OutputNode(
            name=path.name,
            path=str(path),
            kind="directory" if path.is_dir() else "file",
        )
        if not path.is_dir() or depth >= max_depth:
            return node

        children = sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        visible = children[:max_children]
        for child in visible:
            node.children.append(
                self._build_tree(child, depth=depth + 1, max_depth=max_depth, max_children=max_children)
            )
        hidden = len(children) - len(visible)
        if hidden > 0:
            node.children.append(
                OutputNode(
                    name=f"... ({hidden} more items)",
                    path=str(path),
                    kind="truncated",
                )
            )
        return node
