"""Model price constants ($ per 1k tokens). Verified/updated in Phase 0."""

# (input_$/1k, output_$/1k) — OpenAI public pricing as of 2026-07
PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.0025, 0.01),
    # Anthropic placeholders — fill when ANTHROPIC_API_KEY is funded
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-sonnet-4-5-20250929": (0.003, 0.015),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = PRICES.get(model, (0.0, 0.0))
    return (input_tokens / 1000.0) * inp + (output_tokens / 1000.0) * out
