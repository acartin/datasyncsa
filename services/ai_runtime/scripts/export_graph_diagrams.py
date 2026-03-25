#!/usr/bin/env python3
"""Export Mermaid and SVG diagrams for the active ai-runtime LangGraphs."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from html import escape
from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.ai_runtime.graph.generic.graph import build_generic_graph  # noqa: E402
from services.ai_runtime.graph.realtor.graph import build_realtor_graph  # noqa: E402


START = "__start__"
END = "__end__"
OUTPUT_DIR = REPO_ROOT / "services" / "ai_runtime" / "docs" / "graphs"


@dataclass(frozen=True, slots=True)
class NodeSpec:
    name: str
    kind: str = "node"


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    source: str
    target: str
    label: str | None = None
    kind: str = "direct"


@dataclass(frozen=True, slots=True)
class GraphSpec:
    name: str
    nodes: list[NodeSpec]
    edges: list[EdgeSpec]


def _build_spec(name: str, builder) -> GraphSpec:
    compiled = builder(SimpleNamespace())
    workflow = compiled.builder

    router_sources = set(workflow.branches.keys())
    node_order: list[NodeSpec] = [NodeSpec(name=START, kind="start")]
    for node_name in workflow.nodes.keys():
        node_order.append(NodeSpec(name=node_name, kind="node"))
        if node_name in router_sources:
            node_order.append(NodeSpec(name=_router_name(node_name), kind="router"))
    node_order.append(NodeSpec(name=END, kind="end"))
    edges: list[EdgeSpec] = []

    for source, target in sorted(workflow.edges):
        edges.append(EdgeSpec(source=source, target=target))

    for source, branches in workflow.branches.items():
        router_name = _router_name(source)
        edges.append(EdgeSpec(source=source, target=router_name, kind="router_link"))
        for _, branch_spec in branches.items():
            for label, target in branch_spec.ends.items():
                edges.append(
                    EdgeSpec(
                        source=router_name,
                        target=target,
                        label=str(label),
                        kind="conditional",
                    )
                )

    return GraphSpec(name=name, nodes=node_order, edges=edges)


def _display_name(name: str) -> str:
    if name == START:
        return "START"
    if name == END:
        return "END"
    return name


def _router_name(source: str) -> str:
    return f"after_{source}"


def _node_id(name: str) -> str:
    return "n_" + "".join(ch if ch.isalnum() else "_" for ch in name)


def _to_mermaid(spec: GraphSpec) -> str:
    lines = [
        "---",
        f"title: ai-runtime {spec.name} graph",
        "---",
        "flowchart TD",
    ]

    for node in spec.nodes:
        mermaid_id = _node_id(node.name)
        label = _display_name(node.name)
        if node.kind == "start":
            lines.append(f"    {mermaid_id}([START])")
        elif node.kind == "end":
            lines.append(f"    {mermaid_id}((END))")
        elif node.kind == "router":
            lines.append(f"    {mermaid_id}{{{label}}}")
        else:
            lines.append(f"    {mermaid_id}[{label}]")

    for edge in spec.edges:
        source = _node_id(edge.source)
        target = _node_id(edge.target)
        if edge.label:
            lines.append(f"    {source} -->|{edge.label}| {target}")
        else:
            lines.append(f"    {source} --> {target}")

    return "\n".join(lines) + "\n"


def _compute_depths(spec: GraphSpec) -> dict[str, int]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in spec.edges:
        if edge.target == END or edge.source == edge.target:
            continue
        adjacency[edge.source].add(edge.target)

    depths = {START: 0}
    queue: deque[str] = deque([START])
    while queue:
        current = queue.popleft()
        for target in sorted(adjacency.get(current, set())):
            if target not in depths:
                depths[target] = depths[current] + 1
                queue.append(target)

    max_depth = max(depths.values(), default=0)
    for node in spec.nodes:
        if node.name in {START, END}:
            continue
        depths.setdefault(node.name, max_depth + 1)
    depths[END] = max(depths.values(), default=0) + 1
    return depths


def _layout(spec: GraphSpec) -> tuple[dict[str, tuple[float, float]], float, float]:
    depths = _compute_depths(spec)
    order_index = {node.name: index for index, node in enumerate(spec.nodes)}
    rows: dict[int, list[str]] = defaultdict(list)
    for node, depth in depths.items():
        rows[depth].append(node)

    for nodes in rows.values():
        nodes.sort(key=lambda item: order_index[item])

    node_width = 220
    node_height = 58
    x_gap = 70
    y_gap = 92
    margin_x = 40
    margin_y = 50

    positions: dict[str, tuple[float, float]] = {}
    max_cols = max((len(nodes) for nodes in rows.values()), default=1)
    max_depth = max(rows.keys(), default=0)
    for depth, nodes in sorted(rows.items()):
        row_width = len(nodes) * node_width + max(len(nodes) - 1, 0) * x_gap
        left = margin_x + ((max_cols * node_width + max(max_cols - 1, 0) * x_gap) - row_width) / 2
        y = margin_y + depth * (node_height + y_gap)
        for column, node in enumerate(nodes):
            x = left + column * (node_width + x_gap)
            positions[node] = (x, y)

    width = margin_x * 2 + max_cols * node_width + max(max_cols - 1, 0) * x_gap
    height = margin_y * 2 + (max_depth + 1) * node_height + max_depth * y_gap
    return positions, width, height


def _edge_path(
    source: tuple[float, float],
    target: tuple[float, float],
    source_depth: int,
    target_depth: int,
) -> tuple[str, tuple[float, float]]:
    node_width = 220
    node_height = 58
    sx, sy = source
    tx, ty = target

    if target_depth > source_depth:
        x1 = sx + node_width / 2
        y1 = sy + node_height
        x2 = tx + node_width / 2
        y2 = ty
        c1x = x1
        c1y = y1 + 40
        c2x = x2
        c2y = y2 - 40
        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2 - 6
        return f"M{x1:.1f},{y1:.1f} C{c1x:.1f},{c1y:.1f} {c2x:.1f},{c2y:.1f} {x2:.1f},{y2:.1f}", (label_x, label_y)

    if target_depth == source_depth and (sx, sy) != (tx, ty):
        x1 = sx + node_width
        y1 = sy + node_height / 2
        x2 = tx
        y2 = ty + node_height / 2
        curve = abs(x2 - x1) * 0.35
        label_x = (x1 + x2) / 2
        label_y = y1 - 10
        return f"M{x1:.1f},{y1:.1f} C{x1 + curve:.1f},{y1:.1f} {x2 - curve:.1f},{y2:.1f} {x2:.1f},{y2:.1f}", (label_x, label_y)

    if (sx, sy) == (tx, ty):
        x1 = sx + node_width
        y1 = sy + node_height / 2 - 8
        label_x = x1 + 38
        label_y = sy - 8
        return (
            f"M{x1:.1f},{y1:.1f} C{x1 + 65:.1f},{y1 - 35:.1f} {x1 + 65:.1f},{y1 + 65:.1f} {x1:.1f},{y1 + 30:.1f}",
            (label_x, label_y),
        )

    x1 = sx + node_width
    y1 = sy + node_height / 2
    x2 = tx + node_width / 2
    y2 = ty + node_height
    label_x = (x1 + x2) / 2
    label_y = min(y1, y2) - 12
    return f"M{x1:.1f},{y1:.1f} C{x1 + 45:.1f},{y1 - 55:.1f} {x2 - 45:.1f},{y2 + 55:.1f} {x2:.1f},{y2:.1f}", (label_x, label_y)


def _label_lines(label: str, *, max_chars: int = 22) -> list[str]:
    if len(label) <= max_chars:
        return [label]
    parts = label.split("_")
    lines: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current}_{part}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = part
    if current:
        lines.append(current)
    if len(lines) <= 3:
        return lines
    return [lines[0], lines[1], "_".join(lines[2:])]


def _append_multiline_text(parts: list[str], *, center_x: float, center_y: float, lines: list[str], font_size: int = 13) -> None:
    line_height = font_size + 2
    start_y = center_y - ((len(lines) - 1) * line_height) / 2
    parts.append(
        '<text '
        f'x="{center_x:.1f}" y="{start_y:.1f}" '
        'font-family="Arial, sans-serif" text-anchor="middle" fill="#0f172a">'
    )
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        parts.append(f'<tspan x="{center_x:.1f}" dy="{dy}" font-size="{font_size}">{escape(line)}</tspan>')
    parts.append("</text>")


def _to_svg(spec: GraphSpec) -> str:
    positions, width, height = _layout(spec)
    depths = _compute_depths(spec)
    node_width = 220
    node_height = 58

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">',
        "<defs>",
        '<marker id="arrow-direct" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L10,4 L0,8 z" fill="#334155" />',
        "</marker>",
        '<marker id="arrow-conditional" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L10,4 L0,8 z" fill="#2563eb" />',
        "</marker>",
        '<marker id="arrow-router" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L10,4 L0,8 z" fill="#b45309" />',
        "</marker>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#f8fafc" />',
        '<text x="40" y="28" font-size="20" font-family="Arial, sans-serif" font-weight="700" fill="#0f172a">'
        + escape(f"ai-runtime {spec.name} graph")
        + "</text>",
        '<text x="40" y="46" font-size="11" font-family="Arial, sans-serif" fill="#475569">solid = direct | amber = router handoff | dashed blue = router output</text>',
    ]

    for edge in spec.edges:
        source = positions[edge.source]
        target = positions[edge.target]
        path_d, (label_x, label_y) = _edge_path(source, target, depths[edge.source], depths[edge.target])
        if edge.kind == "conditional":
            parts.append(
                f'<path d="{path_d}" fill="none" stroke="#2563eb" stroke-width="2" stroke-dasharray="7 5" marker-end="url(#arrow-conditional)" />'
            )
        elif edge.kind == "router_link":
            parts.append(f'<path d="{path_d}" fill="none" stroke="#b45309" stroke-width="2.2" marker-end="url(#arrow-router)" />')
        else:
            parts.append(f'<path d="{path_d}" fill="none" stroke="#334155" stroke-width="2.2" marker-end="url(#arrow-direct)" />')
        if edge.label:
            parts.append(
                '<text '
                f'x="{label_x:.1f}" y="{label_y:.1f}" '
                'font-size="11" font-family="Arial, sans-serif" text-anchor="middle" '
                'fill="#1d4ed8" stroke="#f8fafc" stroke-width="3" paint-order="stroke">'
                + escape(edge.label)
                + "</text>"
            )

    for node in spec.nodes:
        x, y = positions[node.name]
        label = _display_name(node.name)
        label_lines = _label_lines(label, max_chars=18 if node.kind == "router" else 22)
        if node.kind == "start":
            fill = "#dcfce7"
            stroke = "#16a34a"
        elif node.kind == "end":
            fill = "#fee2e2"
            stroke = "#dc2626"
        elif node.kind == "router":
            fill = "#fff7ed"
            stroke = "#b45309"
        else:
            fill = "#ffffff"
            stroke = "#475569"
        if node.kind == "router":
            cx = x + node_width / 2
            cy = y + node_height / 2
            parts.append(
                f'<polygon points="{cx:.1f},{y:.1f} {x + node_width:.1f},{cy:.1f} {cx:.1f},{y + node_height:.1f} {x:.1f},{cy:.1f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            )
            _append_multiline_text(parts, center_x=cx, center_y=cy, lines=label_lines, font_size=12)
        else:
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_width}" height="{node_height}" rx="14" ry="14" fill="{fill}" stroke="{stroke}" stroke-width="2" />'
            )
            _append_multiline_text(
                parts,
                center_x=x + node_width / 2,
                center_y=y + node_height / 2 + 2,
                lines=label_lines,
                font_size=13,
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def export_graph_diagrams() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    specs = [
        _build_spec("generic", build_generic_graph),
        _build_spec("realtor", build_realtor_graph),
    ]
    written: list[Path] = []

    for spec in specs:
        mermaid_path = OUTPUT_DIR / f"{spec.name}-graph.mmd"
        svg_path = OUTPUT_DIR / f"{spec.name}-graph.svg"
        mermaid_path.write_text(_to_mermaid(spec), encoding="utf-8")
        svg_path.write_text(_to_svg(spec), encoding="utf-8")
        written.extend([mermaid_path, svg_path])

    return written


def main() -> int:
    written = export_graph_diagrams()
    for path in written:
        print(path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
