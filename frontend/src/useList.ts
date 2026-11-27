import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

export function useList<T>(path: string) {
  const [items, setItems] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    api.get<T[]>(path).then(setItems).catch((e) => setError(String(e)));
  }, [path]);
  useEffect(reload, [reload]);
  return { items, reload, error, setError };
}
