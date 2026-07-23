/** Format HQ list pagination chrome: "showing N of Total". */
export function showingOfTotal(shown: number, total: number): string {
  const n = Number.isFinite(shown) ? Math.max(0, Math.floor(shown)) : 0;
  const t = Number.isFinite(total) ? Math.max(0, Math.floor(total)) : n;
  if (t <= 0 && n <= 0) return "showing 0 of 0";
  return `showing ${n} of ${t}`;
}
