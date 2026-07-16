import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchCorrectionCapabilities,
  fetchCorrections,
  purgeCorrections,
  type CorrectionCapabilities,
  type CorrectionList,
  type CorrectionProposal,
} from "./corrections";
import { DATA_GENERATION_CHANGED_EVENT } from "./data-refresh-context";

const EMPTY_LIST: CorrectionList = {
  schema_version: "0.1.0",
  items: [],
  total: 0,
  limit: 100,
  offset: 0,
};

export interface CorrectionController {
  supported: boolean;
  capabilities: CorrectionCapabilities | null;
  list: CorrectionList;
  loading: boolean;
  loadingMore: boolean;
  error: Error | null;
  acceptedByMatch: ReadonlyMap<string, CorrectionProposal[]>;
  reload: () => Promise<void>;
  loadMore: () => Promise<void>;
  removeAll: () => Promise<void>;
}

export const CorrectionContext = createContext<CorrectionController | null>(null);

export function mergeCorrectionLists(
  current: CorrectionList,
  page: CorrectionList,
): CorrectionList {
  const seen = new Set(current.items.map((item) => item.proposal_id));
  const items = [
    ...current.items,
    ...page.items.filter((item) => !seen.has(item.proposal_id)),
  ];
  return { ...current, items, total: page.total, offset: 0 };
}

export function annotationIsCurrent(
  proposal: CorrectionProposal,
  currentIndexFingerprint: string | null | undefined,
): boolean {
  return Boolean(
    currentIndexFingerprint &&
      proposal.local_visibility === "local_annotation" &&
      proposal.target.index_fingerprint === currentIndexFingerprint,
  );
}

export function useCorrectionController(backendReady: boolean): CorrectionController {
  const [capabilities, setCapabilities] = useState<CorrectionCapabilities | null>(null);
  const [list, setList] = useState<CorrectionList>(EMPTY_LIST);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const loadingMoreRef = useRef(false);

  const reload = useCallback(async () => {
    if (!backendReady) return;
    setLoading(true);
    setError(null);
    try {
      const [nextCapabilities, nextList] = await Promise.all([
        fetchCorrectionCapabilities(),
        fetchCorrections(),
      ]);
      setCapabilities(nextCapabilities);
      setList(nextList);
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setLoading(false);
    }
  }, [backendReady]);

  const loadMore = useCallback(async () => {
    if (!backendReady || loadingMoreRef.current || list.items.length >= list.total) return;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await fetchCorrections(100, list.items.length);
      setList((current) => mergeCorrectionLists(current, page));
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [backendReady, list.items.length, list.total]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!backendReady) return;
    const recheck = () => void reload();
    window.addEventListener(DATA_GENERATION_CHANGED_EVENT, recheck);
    return () => window.removeEventListener(DATA_GENERATION_CHANGED_EVENT, recheck);
  }, [backendReady, reload]);

  const removeAll = useCallback(async () => {
    await purgeCorrections();
    setList(EMPTY_LIST);
    await reload();
  }, [reload]);

  const acceptedByMatch = useMemo(() => {
    const result = new Map<string, CorrectionProposal[]>();
    for (const item of list.items) {
      const matchId = item.target.match_id;
      if (!matchId) continue;
      // A source refresh can change the authoritative base beneath an accepted
      // annotation. Hide it until explicit revalidation instead of letting a
      // once-valid local claim silently survive a new index generation.
      if (!annotationIsCurrent(item, capabilities?.current_index_fingerprint)) {
        continue;
      }
      result.set(matchId, [...(result.get(matchId) ?? []), item]);
    }
    return result;
  }, [capabilities?.current_index_fingerprint, list.items]);

  return {
    supported: backendReady && capabilities?.supported === true,
    capabilities,
    list,
    loading,
    loadingMore,
    error,
    acceptedByMatch,
    reload,
    loadMore,
    removeAll,
  };
}

export function useCorrections(): CorrectionController {
  const value = useContext(CorrectionContext);
  if (!value) throw new Error("useCorrections must be used inside CorrectionContext.Provider");
  return value;
}
