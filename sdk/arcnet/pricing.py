"""Model price constants ($ per 1k tokens). Verified/updated in Phase 0."""

# (input_$/1k, output_$/1k) — catalog-aligned as of 2026-07e
PRICES: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.001, 0.006),
    "gpt-5.6-terra": (0.0025, 0.015),
    "gpt-5.6-sol": (0.005, 0.03),
    "legacy-baseline-v1": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    "claude-opus-5": (0.005, 0.025),
    "claude-opus-4-8": (0.005, 0.025),
    "claude-fable-5": (0.01, 0.05),
    "claude-sonnet-5": (0.002, 0.01),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-sonnet-4-5-20250929": (0.003, 0.015),
}

# Bare catalog ids (docs/27 model_catalog) -> dated Anthropic API slugs in PRICES.
CATALOG_ID_ALIASES: dict[str, str] = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def resolve_price_key(model: str) -> str:
    """Map bare catalog id to PRICES key when an alias exists."""
    return CATALOG_ID_ALIASES.get(model, model)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = PRICES.get(resolve_price_key(model), (0.0, 0.0))
    return (input_tokens / 1000.0) * inp + (output_tokens / 1000.0) * out
