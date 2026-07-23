"""Static dated model catalog for ArcNet model intelligence (docs/27).

Prices are **catalog list-price estimates** only — never measured spend.
Update cadence: bump CATALOG_VERSION (YYYY-MM) when refreshing rows.
"""

from __future__ import annotations

from typing import Any, Literal

CATALOG_VERSION = "2026-07"
PRICE_LABEL = f"catalog list-price estimate as of {CATALOG_VERSION}"

Tier = Literal["frontier_reasoning", "reasoning", "standard", "fast"]

# Prices: USD per million tokens (list-price estimate, not measured).
MODELS: list[dict[str, Any]] = [
    # OpenAI — GPT-5 class + o-series
    {
        "id": "gpt-5",
        "provider": "openai",
        "tier": "frontier_reasoning",
        "input_usd_per_mtok": 5.0,
        "output_usd_per_mtok": 15.0,
        "context_window": 400_000,
        "reasoning": True,
        "strengths": "flagship general + long-horizon tool use",
    },
    {
        "id": "gpt-5-mini",
        "provider": "openai",
        "tier": "standard",
        "input_usd_per_mtok": 0.4,
        "output_usd_per_mtok": 1.6,
        "context_window": 200_000,
        "reasoning": False,
        "strengths": "balanced cost/quality default",
    },
    {
        "id": "gpt-5-nano",
        "provider": "openai",
        "tier": "fast",
        "input_usd_per_mtok": 0.1,
        "output_usd_per_mtok": 0.4,
        "context_window": 128_000,
        "reasoning": False,
        "strengths": "cheap high-volume batch",
    },
    {
        "id": "o3",
        "provider": "openai",
        "tier": "frontier_reasoning",
        "input_usd_per_mtok": 10.0,
        "output_usd_per_mtok": 40.0,
        "context_window": 200_000,
        "reasoning": True,
        "strengths": "deep multi-step reasoning under adversarial load",
    },
    {
        "id": "o4-mini",
        "provider": "openai",
        "tier": "reasoning",
        "input_usd_per_mtok": 1.1,
        "output_usd_per_mtok": 4.4,
        "context_window": 200_000,
        "reasoning": True,
        "strengths": "tool-heavy reasoning at mid cost",
    },
    {
        "id": "o3-mini",
        "provider": "openai",
        "tier": "reasoning",
        "input_usd_per_mtok": 1.1,
        "output_usd_per_mtok": 4.4,
        "context_window": 200_000,
        "reasoning": True,
        "strengths": "compact reasoning tier",
    },
    {
        "id": "gpt-4o",
        "provider": "openai",
        "tier": "standard",
        "input_usd_per_mtok": 2.5,
        "output_usd_per_mtok": 10.0,
        "context_window": 128_000,
        "reasoning": False,
        "strengths": "reliable multimodal workhorse",
    },
    {
        "id": "gpt-4o-mini",
        "provider": "openai",
        "tier": "fast",
        "input_usd_per_mtok": 0.15,
        "output_usd_per_mtok": 0.6,
        "context_window": 128_000,
        "reasoning": False,
        "strengths": "low-cost baseline / batch",
    },
    {
        "id": "gpt-4.1",
        "provider": "openai",
        "tier": "standard",
        "input_usd_per_mtok": 2.0,
        "output_usd_per_mtok": 8.0,
        "context_window": 1_000_000,
        "reasoning": False,
        "strengths": "long-context instruction following",
    },
    {
        "id": "gpt-4.1-mini",
        "provider": "openai",
        "tier": "fast",
        "input_usd_per_mtok": 0.4,
        "output_usd_per_mtok": 1.6,
        "context_window": 1_000_000,
        "reasoning": False,
        "strengths": "cheap long-context",
    },
    # Anthropic
    {
        "id": "claude-opus-4-8",
        "provider": "anthropic",
        "tier": "frontier_reasoning",
        "input_usd_per_mtok": 15.0,
        "output_usd_per_mtok": 75.0,
        "context_window": 200_000,
        "reasoning": True,
        "strengths": "highest-stakes analysis and refusal discipline",
    },
    {
        "id": "claude-sonnet-5",
        "provider": "anthropic",
        "tier": "standard",
        "input_usd_per_mtok": 3.0,
        "output_usd_per_mtok": 15.0,
        "context_window": 200_000,
        "reasoning": False,
        "strengths": "strong coding + tool loops",
    },
    {
        "id": "claude-haiku-4-5",
        "provider": "anthropic",
        "tier": "fast",
        "input_usd_per_mtok": 1.0,
        "output_usd_per_mtok": 5.0,
        "context_window": 200_000,
        "reasoning": False,
        "strengths": "fast cheap anthropic tier",
    },
    # Google
    {
        "id": "gemini-3-pro",
        "provider": "google",
        "tier": "frontier_reasoning",
        "input_usd_per_mtok": 1.25,
        "output_usd_per_mtok": 5.0,
        "context_window": 1_000_000,
        "reasoning": True,
        "strengths": "long-context multimodal reasoning",
    },
    {
        "id": "gemini-3-flash",
        "provider": "google",
        "tier": "fast",
        "input_usd_per_mtok": 0.15,
        "output_usd_per_mtok": 0.6,
        "context_window": 1_000_000,
        "reasoning": False,
        "strengths": "high-throughput long context",
    },
    # Moonshot
    {
        "id": "kimi-k3",
        "provider": "moonshot",
        "tier": "reasoning",
        "input_usd_per_mtok": 0.6,
        "output_usd_per_mtok": 2.5,
        "context_window": 256_000,
        "reasoning": True,
        "strengths": "long-context agentic coding",
    },
    # xAI
    {
        "id": "grok-4.5",
        "provider": "xai",
        "tier": "frontier_reasoning",
        "input_usd_per_mtok": 3.0,
        "output_usd_per_mtok": 15.0,
        "context_window": 256_000,
        "reasoning": True,
        "strengths": "real-time knowledge + strong reasoning",
    },
    {
        "id": "grok-4.5-mini",
        "provider": "xai",
        "tier": "fast",
        "input_usd_per_mtok": 0.3,
        "output_usd_per_mtok": 1.2,
        "context_window": 128_000,
        "reasoning": False,
        "strengths": "cheap grok-class throughput",
    },
]

_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in MODELS}

VALID_TIERS = frozenset({"frontier_reasoning", "reasoning", "standard", "fast"})


def catalog_version() -> str:
    return CATALOG_VERSION


def price_label() -> str:
    return PRICE_LABEL


def list_models() -> list[dict[str, Any]]:
    """Return shallow copies of catalog rows (immutable snapshot)."""
    return [dict(m) for m in MODELS]


def get_model(model_id: str | None) -> dict[str, Any] | None:
    if not model_id:
        return None
    row = _BY_ID.get(str(model_id).strip())
    return dict(row) if row else None


def project_cost_usd(
    model_id: str | None,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """List-price projection from catalog rates. None if model unknown."""
    row = get_model(model_id)
    if row is None:
        return None
    inp = max(0, int(input_tokens or 0))
    out = max(0, int(output_tokens or 0))
    return (inp / 1_000_000.0) * float(row["input_usd_per_mtok"]) + (
        out / 1_000_000.0
    ) * float(row["output_usd_per_mtok"])


def catalog_integrity_errors() -> list[str]:
    """Validate static catalog shape — used by tests."""
    errs: list[str] = []
    if not CATALOG_VERSION or not isinstance(CATALOG_VERSION, str):
        errs.append("CATALOG_VERSION missing")
    seen: set[str] = set()
    for i, m in enumerate(MODELS):
        mid = m.get("id")
        if not isinstance(mid, str) or not mid:
            errs.append(f"row[{i}]: id required")
            continue
        if mid in seen:
            errs.append(f"duplicate id {mid}")
        seen.add(mid)
        if m.get("provider") not in (
            "openai",
            "anthropic",
            "google",
            "moonshot",
            "xai",
        ):
            errs.append(f"{mid}: unknown provider")
        if m.get("tier") not in VALID_TIERS:
            errs.append(f"{mid}: tier must be one of {sorted(VALID_TIERS)}")
        for k in ("input_usd_per_mtok", "output_usd_per_mtok"):
            v = m.get(k)
            if not isinstance(v, (int, float)) or float(v) < 0:
                errs.append(f"{mid}: {k} must be non-negative number")
        cw = m.get("context_window")
        if not isinstance(cw, int) or cw <= 0:
            errs.append(f"{mid}: context_window must be positive int")
        if not isinstance(m.get("reasoning"), bool):
            errs.append(f"{mid}: reasoning must be bool")
        if not isinstance(m.get("strengths"), str) or not m["strengths"]:
            errs.append(f"{mid}: strengths one-liner required")
    return errs
