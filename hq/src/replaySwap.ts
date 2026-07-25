/** Pure helpers for Time Machine model vs prompt swap axis. */

import type { ReplayRow } from "./apiResilience.ts";

export type ReplaySwapAxis = "model" | "prompt";

export type ReplaySwapChoice = {
  candidate_model?: string;
  candidate_prompt?: string;
};

export function replaySwapAxis(model: string, prompt: string): "model" | "prompt" | "none" | "both" {
  const m = model.trim();
  const p = prompt.trim();
  if (m && p) return "both";
  if (m) return "model";
  if (p) return "prompt";
  return "none";
}

export function canRunReplaySwap(model: string, prompt: string): boolean {
  return replaySwapAxis(model, prompt) === "model" || replaySwapAxis(model, prompt) === "prompt";
}

export function replaySwapChoice(model: string, prompt: string): ReplaySwapChoice | null {
  const axis = replaySwapAxis(model, prompt);
  if (axis === "model") return { candidate_model: model.trim() };
  if (axis === "prompt") return { candidate_prompt: prompt.trim() };
  return null;
}

export function replaySwapValidationMessage(model: string, prompt: string): string | null {
  const axis = replaySwapAxis(model, prompt);
  if (axis === "both") {
    return "provide exactly one of candidate_model or candidate_prompt";
  }
  if (axis === "none") {
    return "pick candidate_model or candidate_prompt before replay.run()";
  }
  return null;
}

export function replayHistoryAxis(row: ReplayRow): ReplaySwapAxis | "unknown" {
  if (row.candidate_model) return "model";
  if (row.candidate_prompt_ref) return "prompt";
  return "unknown";
}

export function replayHistoryLabel(row: ReplayRow): string {
  const axis = replayHistoryAxis(row);
  if (axis === "model") return `model=${row.candidate_model}`;
  if (axis === "prompt") return `prompt=${row.candidate_prompt_ref}`;
  return "?";
}

export function replaySwapAxisTag(axis: ReplaySwapAxis | "unknown"): string {
  if (axis === "model") return "[model-swap]";
  if (axis === "prompt") return "[prompt-swap]";
  return "[?]";
}
