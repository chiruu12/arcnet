"""Minimal TOON encoder for agent-view envelopes (https://toonformat.dev/)."""

from __future__ import annotations

from typing import Any


def _esc_cell(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if "," in s or '"' in s or "\n" in s:
        return f'"{s.replace(chr(34), chr(34) * 2)}"'
    return s


def _is_primitive(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


def _uniform_object_array(rows: list[Any]) -> bool:
    if not rows or not all(isinstance(r, dict) for r in rows):
        return False
    keys = [tuple(sorted(r.keys())) for r in rows]  # type: ignore[union-attr]
    return len(set(keys)) == 1 and len(keys[0]) > 0


def _tabular(name: str, rows: list[dict[str, Any]], indent: int = 0) -> str:
    pad = "  " * indent
    if not rows:
        return f"{pad}{name}[0]{{}}:"
    fields = list(rows[0].keys())
    header = f"{pad}{name}[{len(rows)}]{{{','.join(fields)}}}:"
    body = [
        f"{pad}  {','.join(_esc_cell(row.get(f)) for f in fields)}" for row in rows
    ]
    return "\n".join([header, *body])


def encode_toon(value: Any, indent: int = 0) -> str:
    """Encode JSON-compatible value as TOON text."""
    pad = "  " * indent
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if "\n" in value or ":" in value or "," in value:
            return f'"{value.replace(chr(34), chr(34) * 2)}"'
        return value
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        if _uniform_object_array(value):
            return _tabular("items" if indent else "rows", value, indent)  # type: ignore[arg-type]
        if all(_is_primitive(x) for x in value):
            return f"{pad}{','.join(_esc_cell(x) for x in value)}"
        lines: list[str] = []
        for i, item in enumerate(value):
            block = encode_toon(item, indent + 1)
            lines.append(f"{pad}- [{i}]")
            lines.append(block)
        return "\n".join(lines)
    if isinstance(value, dict):
        lines: list[str] = []
        for key, val in value.items():
            if val is None:
                continue
            if _is_primitive(val):
                lines.append(f"{pad}{key}: {encode_toon(val, 0)}")
            elif isinstance(val, list) and _uniform_object_array(val):
                lines.append(_tabular(str(key), val, indent))  # type: ignore[arg-type]
            elif isinstance(val, list) and all(_is_primitive(x) for x in val):
                lines.append(f"{pad}{key}[{len(val)}]: {','.join(_esc_cell(x) for x in val)}")
            elif isinstance(val, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(encode_toon(val, indent + 1))
            else:
                lines.append(f"{pad}{key}: {_esc_cell(val)}")
        return "\n".join(lines)
    return _esc_cell(value)


def envelope_to_toon(envelope: dict[str, Any]) -> str:
    """Encode standard agent-view envelope."""
    parts = [
        f"view: {envelope.get('view', '')}",
        f"id: {envelope.get('id', '')}",
        f"generated_at: {envelope.get('generated_at', '')}",
        "links:",
        encode_toon(envelope.get("links") or {}, 1),
        "hints:",
        encode_toon(envelope.get("hints") or {}, 1),
        "data:",
        encode_toon(envelope.get("data") or {}, 1),
    ]
    return "\n".join(parts)
