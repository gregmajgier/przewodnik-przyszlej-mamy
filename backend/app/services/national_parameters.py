"""Nadzorcze zmiany parametrów silnika krajowego.

To celowo nie edytuje plików seedowych ani nie zastępuje danych ZUS.
Zmiany są demonstracyjnymi override'ami trzymanymi w Store i można je resetować.
"""

from __future__ import annotations

import copy
from typing import Any


def apply_overrides(tree: dict, overrides: dict) -> dict:
    result = copy.deepcopy(tree)
    for path, value in overrides.items():
        set_at_path(result, path, value)
    return result


def set_at_path(tree: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = tree
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def flatten_leaves(tree: dict, prefix: str = "") -> list[dict]:
    rows: list[dict] = []
    for key in sorted(tree):
        path = f"{prefix}.{key}" if prefix else key
        value = tree[key]
        if isinstance(value, dict):
            rows.extend(flatten_leaves(value, path))
        elif isinstance(value, (bool, int, float, str)):
            rows.append({"path": path, "value": value, "type": type(value).__name__})
    return rows
