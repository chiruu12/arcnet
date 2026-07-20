"""Seeded customer DB + demo tools for Agent J."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agno.tools.decorator import tool

from arcnet.guardrail import retrieval_post_hook

FIXTURES = Path(__file__).resolve().parents[1] / "scenarios" / "fixtures"
CUSTOMERS_PATH = FIXTURES / "customers.json"
PAGES: dict[str, Path] = {
    "https://bug-planet.example/shipping/4415": FIXTURES / "shipping_poisoned.html",
    "shipping/4415": FIXTURES / "shipping_poisoned.html",
}


def load_customers() -> list[dict[str, Any]]:
    return json.loads(CUSTOMERS_PATH.read_text())


def find_order(order_id: str) -> dict[str, Any] | None:
    oid = order_id.lstrip("#")
    for c in load_customers():
        for o in c.get("orders") or []:
            if str(o.get("order_id")) == oid:
                return {"customer": c, "order": o}
    return None


@tool(post_hook=retrieval_post_hook)
def fetch_url(url: str) -> str:
    """Fetch a URL and return page text (demo: local fixtures only)."""
    path = PAGES.get(url)
    if path is None:
        # fuzzy match by suffix
        for key, p in PAGES.items():
            if url.endswith(key) or key in url:
                path = p
                break
    if path is None or not path.exists():
        return f"404 Not Found: {url}"
    return path.read_text()


@tool
def lookup_customer(order_id: str) -> str:
    """Look up a customer order by id (e.g. 4415). Returns status without SSN."""
    hit = find_order(order_id)
    if hit is None:
        return f"No order found for #{order_id.lstrip('#')}"
    c, o = hit["customer"], hit["order"]
    return (
        f"order=#{o['order_id']} customer={c['name']} email={c['email']} "
        f"status={o['status']} carrier={o.get('carrier')} eta={o.get('eta')}"
    )


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email (side-effect tool — guarded against taint exfil)."""
    return f"EMAIL_SENT to={to} subject={subject} bytes={len(body)}"


@tool
def run_query(sql: str) -> str:
    """Run a read-only demo SQL query against the seeded customer store."""
    lowered = sql.strip().lower()
    if any(tok in lowered for tok in ("drop ", "delete ", "truncate ", "alter ")):
        # Real block is in tool_call middleware; this is a last-line demo safety.
        return "REFUSED: destructive SQL not allowed"
    if "4415" in sql or "order" in lowered:
        hit = find_order("4415")
        if hit:
            return json.dumps({"order": hit["order"], "customer_name": hit["customer"]["name"]})
    return json.dumps({"rows": []})


TOOLS = [fetch_url, lookup_customer, send_email, run_query]
