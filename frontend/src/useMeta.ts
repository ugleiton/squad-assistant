import { useEffect, useState } from "react";
import { api, Meta } from "./api";

let cache: Promise<Meta> | null = null;

export function useMeta(): Meta | undefined {
  const [meta, setMeta] = useState<Meta>();
  useEffect(() => {
    cache ??= api.get<Meta>("/meta");
    cache.then(setMeta).catch(() => (cache = null));
  }, []);
  return meta;
}
