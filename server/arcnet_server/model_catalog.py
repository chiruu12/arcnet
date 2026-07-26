"""Static dated model catalog for ArcNet model intelligence (docs/27).

Prices are **catalog list-price estimates** only — never measured spend.
Update cadence: bump CATALOG_VERSION when refreshing rows.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

CATALOG_VERSION = "2026-07e"
PRICE_LABEL = f"catalog list-price estimate as of {CATALOG_VERSION}"

# Surfaced first in HQ model intel — bump with CATALOG_VERSION when adding rows.
CATALOG_HIGHLIGHT_IDS: frozenset[str] = frozenset(
    {
        "kimi-k2.7-code",
        "kimi-k3",
        "qwen3.8-max-preview",
        "qwen3.6-35b-a3b",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    }
)

CapabilityTier = Literal["frontier", "high", "mid", "light"]
CostClass = Literal["premium", "standard", "economy"]
ModelStatus = Literal["current", "preview", "legacy", "deprecated"]

CAPABILITY_ORDER = {"frontier": 4, "high": 3, "mid": 2, "light": 1}
STATUS_ORDER = {"current": 4, "preview": 3, "legacy": 2, "deprecated": 1}

PRICE_VERIFIED = "2026-07-25"


def _m(
    *,
    id: str,
    provider: str,
    display_name: str,
    capability_tier: CapabilityTier,
    cost_class: CostClass,
    input_usd_per_mtok: float,
    output_usd_per_mtok: float,
    context_window: int,
    strengths: str,
    status: ModelStatus = "current",
    cached_input_usd_per_mtok: float | None = None,
    max_output_tokens: int | None = None,
    reasoning: bool = False,
    reasoning_control: str = "none",
    released: str | None = None,
    knowledge_cutoff: str | None = None,
    caveats: list[str] | None = None,
    source_url: str = "",
    long_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cached = (
        float(cached_input_usd_per_mtok)
        if cached_input_usd_per_mtok is not None
        else float(input_usd_per_mtok) * 0.1
    )
    row: dict[str, Any] = {
        "id": id,
        "provider": provider,
        "display_name": display_name,
        "capability_tier": capability_tier,
        "cost_class": cost_class,
        "tier": capability_tier,  # backward-compat alias for docs/12 consumers
        "input_usd_per_mtok": input_usd_per_mtok,
        "cached_input_usd_per_mtok": cached,
        "output_usd_per_mtok": output_usd_per_mtok,
        "context_window": context_window,
        "max_output_tokens": max_output_tokens,
        "reasoning": reasoning,
        "reasoning_control": reasoning_control,
        "status": status,
        "released": released,
        "knowledge_cutoff": knowledge_cutoff,
        "strengths": strengths,
        "caveats": list(caveats or []),
        "source_url": source_url,
        "price_verified": PRICE_VERIFIED if status in ("current", "preview") else None,
    }
    if long_context:
        row["long_context"] = long_context
    return row


# Prices: USD per million tokens (list-price estimate, not measured).
MODELS: list[dict[str, Any]] = [
    # --- OpenAI GPT-5.6 (current) ---
    _m(
        id="gpt-5.6-sol",
        provider="openai",
        display_name="GPT-5.6 Sol",
        capability_tier="frontier",
        cost_class="premium",
        input_usd_per_mtok=5.0,
        cached_input_usd_per_mtok=0.5,
        output_usd_per_mtok=30.0,
        context_window=1_050_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07-09",
        knowledge_cutoff="2026-02-16",
        strengths="frontier reasoning, coding agents, complex multi-step work",
        caveats=["gpt-5.6 alias routes here, not luna or terra"],
        source_url="https://developers.openai.com/api/docs/pricing",
        long_context={
            "threshold_tokens": 272_000,
            "input_usd_per_mtok": 10.0,
            "cached_input_usd_per_mtok": 1.0,
            "output_usd_per_mtok": 45.0,
        },
    ),
    _m(
        id="gpt-5.6-terra",
        provider="openai",
        display_name="GPT-5.6 Terra",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=2.5,
        cached_input_usd_per_mtok=0.25,
        output_usd_per_mtok=15.0,
        context_window=1_050_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07-09",
        knowledge_cutoff="2026-02-16",
        strengths="balanced professional work, analysis, routine coding",
        source_url="https://developers.openai.com/api/docs/pricing",
        long_context={
            "threshold_tokens": 272_000,
            "input_usd_per_mtok": 5.0,
            "cached_input_usd_per_mtok": 0.5,
            "output_usd_per_mtok": 22.5,
        },
    ),
    _m(
        id="gpt-5.6-luna",
        provider="openai",
        display_name="GPT-5.6 Luna",
        capability_tier="mid",
        cost_class="economy",
        input_usd_per_mtok=1.0,
        cached_input_usd_per_mtok=0.1,
        output_usd_per_mtok=6.0,
        context_window=1_050_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07-09",
        knowledge_cutoff="2026-02-16",
        strengths="GPT-5.6 cost-optimized fleet baseline — high-volume agent steps",
        source_url="https://developers.openai.com/api/docs/pricing",
        long_context={
            "threshold_tokens": 272_000,
            "input_usd_per_mtok": 2.0,
            "cached_input_usd_per_mtok": 0.2,
            "output_usd_per_mtok": 9.0,
        },
    ),
    # --- Anthropic (current) ---
    _m(
        id="claude-fable-5",
        provider="anthropic",
        display_name="Claude Fable 5",
        capability_tier="frontier",
        cost_class="premium",
        input_usd_per_mtok=10.0,
        cached_input_usd_per_mtok=1.0,
        output_usd_per_mtok=50.0,
        context_window=1_000_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="always-on adaptive",
        released="2026-07",
        strengths="highest-stakes analysis and refusal discipline",
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
    ),
    _m(
        id="claude-opus-5",
        provider="anthropic",
        display_name="Claude Opus 5",
        capability_tier="frontier",
        cost_class="premium",
        input_usd_per_mtok=5.0,
        cached_input_usd_per_mtok=0.5,
        output_usd_per_mtok=25.0,
        context_window=1_000_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07",
        strengths="frontier coding + agentic tool use at Opus-class pricing",
        caveats=["same list price as Opus 4.8 — upgrade is capability, not cost"],
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
    ),
    _m(
        id="claude-opus-4-8",
        provider="anthropic",
        display_name="Claude Opus 4.8",
        capability_tier="frontier",
        cost_class="premium",
        input_usd_per_mtok=5.0,
        cached_input_usd_per_mtok=0.5,
        output_usd_per_mtok=25.0,
        context_window=1_000_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-06",
        strengths="prior-gen frontier — strong but superseded by Opus 5",
        status="legacy",
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
    ),
    _m(
        id="claude-sonnet-5",
        provider="anthropic",
        display_name="Claude Sonnet 5",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=2.0,
        cached_input_usd_per_mtok=0.2,
        output_usd_per_mtok=10.0,
        context_window=1_000_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07",
        strengths="strong coding + tool loops at intro pricing through Aug 2026",
        caveats=[
            "intro pricing $2/$10 through 2026-08-31, then $3/$15 standard",
            "new tokenizer emits ~1.0–1.35× more tokens than Sonnet 4.6 for same text",
            "at standard pricing, effective cost per unit of work may exceed Sonnet 4.6",
        ],
        source_url="https://www.anthropic.com/news/claude-sonnet-5",
    ),
    _m(
        id="claude-sonnet-4-6",
        provider="anthropic",
        display_name="Claude Sonnet 4.6",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=3.0,
        cached_input_usd_per_mtok=0.3,
        output_usd_per_mtok=15.0,
        context_window=1_000_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="adaptive",
        released="2026-02",
        strengths="proven Sonnet tier — often better value than Sonnet 5 at standard pricing",
        caveats=["prefer over Sonnet 5 unless you need Sonnet 5-specific capability"],
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
    ),
    _m(
        id="claude-haiku-4-5",
        provider="anthropic",
        display_name="Claude Haiku 4.5",
        capability_tier="light",
        cost_class="economy",
        input_usd_per_mtok=1.0,
        cached_input_usd_per_mtok=0.1,
        output_usd_per_mtok=5.0,
        context_window=200_000,
        max_output_tokens=64_000,
        reasoning=True,
        reasoning_control="enabled",
        released="2025-10",
        strengths="fast cheap anthropic tier for batch and routing",
        source_url="https://platform.claude.com/docs/en/about-claude/pricing",
    ),
    # --- Moonshot (verified open-weight) ---
    _m(
        id="kimi-k2.7-code",
        provider="moonshot",
        display_name="Kimi K2.7 Code",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=3.0,
        cached_input_usd_per_mtok=0.3,
        output_usd_per_mtok=15.0,
        context_window=256_000,
        max_output_tokens=131_072,
        reasoning=True,
        reasoning_control="effort",
        released="2026-06",
        strengths="verified open-weight long-horizon coding and multi-step tools",
        caveats=[
            "verified HF repo moonshotai/Kimi-K2.7-Code",
            "replaces unverified kimi-k3 — no official K3 open-weight release found",
            "list rates are Moonshot-tier placeholder; self-hosted has no API meter",
        ],
        source_url="https://huggingface.co/moonshotai/Kimi-K2.7-Code",
    ),
    _m(
        id="kimi-k3",
        provider="moonshot",
        display_name="Kimi K3 (API preview)",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=3.0,
        cached_input_usd_per_mtok=0.3,
        output_usd_per_mtok=15.0,
        context_window=1_048_576,
        max_output_tokens=131_072,
        reasoning=True,
        reasoning_control="always-on",
        status="preview",
        released="2026-07",
        strengths="long-context Moonshot API tier for agentic coding",
        caveats=[
            "API-only — no verified HuggingFace open-weight repo for K3",
            "prefer kimi-k2.7-code for verified open-weight deployment",
            "reasoning tokens billed as output",
        ],
        source_url="https://platform.kimi.ai/docs/pricing/chat-k3",
    ),
    # --- DeepSeek ---
    _m(
        id="deepseek-v4-flash",
        provider="deepseek",
        display_name="DeepSeek V4 Flash",
        capability_tier="light",
        cost_class="economy",
        input_usd_per_mtok=0.14,
        cached_input_usd_per_mtok=0.0028,
        output_usd_per_mtok=0.28,
        context_window=1_000_000,
        max_output_tokens=None,
        reasoning=True,
        reasoning_control="effort",
        released="2026-04",
        strengths="efficient open-weight reasoning, coding, and agent tool use",
        caveats=[
            "official weights are preview",
            "supports non-think, think-high, and think-max modes",
            "384K is a recommended minimum context for Think Max, not max output",
            "public pricing page currently redirects; reverify rates before approval",
        ],
        source_url="https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash",
    ),
    _m(
        id="deepseek-v4-pro",
        provider="deepseek",
        display_name="DeepSeek V4 Pro",
        capability_tier="high",
        cost_class="economy",
        input_usd_per_mtok=0.435,
        cached_input_usd_per_mtok=0.003625,
        output_usd_per_mtok=0.87,
        context_window=1_000_000,
        max_output_tokens=None,
        reasoning=True,
        reasoning_control="effort",
        released="2026-04",
        strengths="open-weight SOTA coding at extreme cost efficiency",
        caveats=[
            "official weights are preview",
            "384K is a recommended minimum context for Think Max, not max output",
            "public pricing page currently redirects; reverify rates before approval",
        ],
        source_url="https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro",
    ),
    # --- Alibaba Qwen ---
    _m(
        id="qwen3.8-max-preview",
        provider="alibaba",
        display_name="Qwen 3.8 Max Preview",
        capability_tier="frontier",
        cost_class="premium",
        input_usd_per_mtok=0.0,
        cached_input_usd_per_mtok=0.0,
        output_usd_per_mtok=0.0,
        context_window=983_616,
        max_output_tokens=131_072,
        reasoning=True,
        reasoning_control="effort",
        status="preview",
        released="2026-07-19",
        strengths="2.4T MoE flagship — multimodal reasoning, coding, long docs",
        caveats=[
            "credit-based Token Plan / Qoder — no published per-token API rate yet",
            "preview model may change or be replaced before GA",
            "no verified open-weight HF repo yet — open weights promised later",
        ],
        source_url="https://developer.aliyun.com/article/1750982",
    ),
    _m(
        id="qwen3.6-35b-a3b",
        provider="alibaba",
        display_name="Qwen 3.6 35B A3B",
        capability_tier="high",
        cost_class="economy",
        input_usd_per_mtok=0.0,
        cached_input_usd_per_mtok=0.0,
        output_usd_per_mtok=0.0,
        context_window=262_144,
        max_output_tokens=131_072,
        reasoning=True,
        reasoning_control="effort",
        strengths="verified Apache-2.0 open-weight — agentic coding and native tools",
        caveats=[
            "verified HF repo Qwen/Qwen3.6-35B-A3B",
            "self-hosted — no API meter; list price N/A",
        ],
        source_url="https://huggingface.co/Qwen/Qwen3.6-35B-A3B",
    ),
    # --- Google (preview) ---
    _m(
        id="gemini-3.1-pro",
        provider="google",
        display_name="Gemini 3.1 Pro",
        capability_tier="frontier",
        cost_class="standard",
        input_usd_per_mtok=2.0,
        cached_input_usd_per_mtok=0.2,
        output_usd_per_mtok=12.0,
        context_window=1_000_000,
        max_output_tokens=64_000,
        reasoning=True,
        reasoning_control="effort",
        status="preview",
        released="2026-07",
        strengths="long-context multimodal reasoning",
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
        long_context={
            "threshold_tokens": 200_000,
            "input_usd_per_mtok": 4.0,
            "cached_input_usd_per_mtok": 0.4,
            "output_usd_per_mtok": 18.0,
        },
    ),
    _m(
        id="gemini-3-flash",
        provider="google",
        display_name="Gemini 3 Flash",
        capability_tier="mid",
        cost_class="economy",
        input_usd_per_mtok=0.5,
        cached_input_usd_per_mtok=0.05,
        output_usd_per_mtok=3.0,
        context_window=1_000_000,
        max_output_tokens=64_000,
        reasoning=True,
        reasoning_control="effort",
        status="preview",
        released="2026-07",
        strengths="high-throughput long context at flash pricing",
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
    ),
    # --- xAI ---
    _m(
        id="grok-4.5",
        provider="xai",
        display_name="Grok 4.5",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=2.0,
        cached_input_usd_per_mtok=0.3,
        output_usd_per_mtok=6.0,
        context_window=500_000,
        max_output_tokens=128_000,
        reasoning=True,
        reasoning_control="effort",
        released="2026-07-08",
        knowledge_cutoff="2026-02-01",
        strengths="coding, agentic tasks, real-time knowledge",
        source_url="https://docs.x.ai/developers/pricing",
        long_context={
            "threshold_tokens": 200_000,
            "input_usd_per_mtok": 4.0,
            "cached_input_usd_per_mtok": 0.6,
            "output_usd_per_mtok": 12.0,
        },
    ),
    # --- Legacy (hero replay pricing must keep resolving) ---
    _m(
        id="gpt-4o",
        provider="openai",
        display_name="GPT-4o",
        capability_tier="mid",
        cost_class="standard",
        input_usd_per_mtok=2.5,
        cached_input_usd_per_mtok=0.25,
        output_usd_per_mtok=10.0,
        context_window=128_000,
        max_output_tokens=16_384,
        reasoning=False,
        status="legacy",
        strengths="reliable multimodal workhorse (Time Machine candidate)",
        source_url="https://developers.openai.com/api/docs/pricing",
    ),
    _m(
        id="legacy-baseline-v1",
        provider="openai",
        display_name="Historical baseline v1",
        capability_tier="light",
        cost_class="economy",
        input_usd_per_mtok=0.15,
        cached_input_usd_per_mtok=0.015,
        output_usd_per_mtok=0.6,
        context_window=128_000,
        max_output_tokens=16_384,
        reasoning=False,
        status="legacy",
        strengths="low-cost baseline — hero replay recordings use this model",
        source_url="https://developers.openai.com/api/docs/pricing",
    ),
    _m(
        id="gpt-4.1",
        provider="openai",
        display_name="GPT-4.1",
        capability_tier="mid",
        cost_class="standard",
        input_usd_per_mtok=2.0,
        cached_input_usd_per_mtok=0.2,
        output_usd_per_mtok=8.0,
        context_window=1_000_000,
        max_output_tokens=32_768,
        reasoning=False,
        status="legacy",
        strengths="long-context instruction following",
        source_url="https://developers.openai.com/api/docs/pricing",
    ),
    _m(
        id="o4-mini",
        provider="openai",
        display_name="o4-mini",
        capability_tier="high",
        cost_class="standard",
        input_usd_per_mtok=1.1,
        cached_input_usd_per_mtok=0.11,
        output_usd_per_mtok=4.4,
        context_window=200_000,
        max_output_tokens=100_000,
        reasoning=True,
        reasoning_control="effort",
        status="legacy",
        strengths="tool-heavy reasoning at mid cost (superseded by GPT-5.6)",
        source_url="https://developers.openai.com/api/docs/pricing",
    ),
    _m(
        id="gpt-5-nano",
        provider="openai",
        display_name="GPT-5 nano",
        capability_tier="light",
        cost_class="economy",
        input_usd_per_mtok=0.1,
        cached_input_usd_per_mtok=0.01,
        output_usd_per_mtok=0.4,
        context_window=128_000,
        reasoning=False,
        status="legacy",
        strengths="cheap high-volume batch",
        source_url="https://developers.openai.com/api/docs/pricing",
    ),
]

_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in MODELS}

VALID_CAPABILITY_TIERS = frozenset({"frontier", "high", "mid", "light"})
VALID_COST_CLASSES = frozenset({"premium", "standard", "economy"})
VALID_STATUSES = frozenset({"current", "preview", "legacy", "deprecated"})


def catalog_version() -> str:
    return CATALOG_VERSION


def catalog_highlight_ids() -> frozenset[str]:
    return CATALOG_HIGHLIGHT_IDS


def price_label() -> str:
    return PRICE_LABEL


def list_models(
    *,
    provider: str | None = None,
    status: str | None = None,
    capability_tier: str | None = None,
    min_context: int | None = None,
    reasoning: bool | None = None,
) -> list[dict[str, Any]]:
    """Return shallow copies, optionally filtered."""
    out: list[dict[str, Any]] = []
    for m in MODELS:
        if provider and m.get("provider") != provider:
            continue
        if status and m.get("status") != status:
            continue
        if capability_tier and m.get("capability_tier") != capability_tier:
            continue
        if min_context is not None and int(m.get("context_window") or 0) < min_context:
            continue
        if reasoning is not None and bool(m.get("reasoning")) != reasoning:
            continue
        out.append(dict(m))
    return out


def get_model(model_id: str | None) -> dict[str, Any] | None:
    if not model_id:
        return None
    row = _BY_ID.get(str(model_id).strip())
    return dict(row) if row else None


def capability_rank(tier: str | None) -> int:
    return CAPABILITY_ORDER.get(str(tier or ""), 0)


def status_rank(status: str | None) -> int:
    return STATUS_ORDER.get(str(status or ""), 0)


def project_cost_usd(
    model_id: str | None,
    *,
    input_tokens: int,
    output_tokens: int,
    use_cached_input: bool = False,
) -> float | None:
    """List-price projection from catalog rates. None if model unknown."""
    row = get_model(model_id)
    if row is None:
        return None
    inp = max(0, int(input_tokens or 0))
    out = max(0, int(output_tokens or 0))
    in_rate = (
        float(row["cached_input_usd_per_mtok"])
        if use_cached_input
        else float(row["input_usd_per_mtok"])
    )
    out_rate = float(row["output_usd_per_mtok"])
    if in_rate == 0.0 and out_rate == 0.0 and row.get("status") == "preview":
        return 0.0
    return (inp / 1_000_000.0) * in_rate + (out / 1_000_000.0) * out_rate


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
        prov = m.get("provider")
        if prov not in (
            "openai",
            "anthropic",
            "google",
            "moonshot",
            "xai",
            "deepseek",
            "alibaba",
        ):
            errs.append(f"{mid}: unknown provider {prov}")
        if m.get("capability_tier") not in VALID_CAPABILITY_TIERS:
            errs.append(f"{mid}: invalid capability_tier")
        if m.get("cost_class") not in VALID_COST_CLASSES:
            errs.append(f"{mid}: invalid cost_class")
        if m.get("status") not in VALID_STATUSES:
            errs.append(f"{mid}: invalid status")
        for k in ("input_usd_per_mtok", "output_usd_per_mtok", "cached_input_usd_per_mtok"):
            v = m.get(k)
            if not isinstance(v, (int, float)) or float(v) < 0:
                errs.append(f"{mid}: {k} must be non-negative number")
        cached = float(m.get("cached_input_usd_per_mtok") or 0)
        inp = float(m.get("input_usd_per_mtok") or 0)
        if cached > inp and inp > 0:
            errs.append(f"{mid}: cached_input must be <= input")
        cw = m.get("context_window")
        if not isinstance(cw, int) or cw <= 0:
            errs.append(f"{mid}: context_window must be positive int")
        if not isinstance(m.get("reasoning"), bool):
            errs.append(f"{mid}: reasoning must be bool")
        if not isinstance(m.get("strengths"), str) or not m["strengths"]:
            errs.append(f"{mid}: strengths one-liner required")
        if not isinstance(m.get("display_name"), str) or not m["display_name"]:
            errs.append(f"{mid}: display_name required")
        if m.get("status") in ("current", "preview") and not m.get("price_verified"):
            errs.append(f"{mid}: price_verified required for current/preview")
        if m.get("tier") != m.get("capability_tier"):
            errs.append(f"{mid}: tier alias must match capability_tier")
    for hid in CATALOG_HIGHLIGHT_IDS:
        if hid not in seen:
            errs.append(f"CATALOG_HIGHLIGHT_IDS: unknown id {hid}")
    return errs


def catalog_export() -> dict[str, Any]:
    """Full catalog payload for GET /api/models/catalog."""
    return {
        "catalog_version": catalog_version(),
        "price_label": price_label(),
        "models": list_models(),
        "count": len(MODELS),
    }
