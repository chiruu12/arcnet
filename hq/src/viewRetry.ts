import { useCallback, useState } from "react";

/** Bump to re-run a view's data fetch (include token in useEffect deps). */
export function useRetryToken(): [number, () => void] {
  const [token, setToken] = useState(0);
  const retry = useCallback(() => setToken((t) => t + 1), []);
  return [token, retry];
}
