import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { FollowListResponse, FollowSettings, FollowedMatch } from "./contract";
import {
  HAS_BACKEND,
  claimFollowNotifications,
  fetchFollowSettings,
  fetchFollows,
  followMatch,
  markFollowEventsRead,
  reconcileFollows,
  removeFollowHistory,
  unfollowMatch,
  updateFollowNotification,
  updateFollowSettings,
} from "./api";
import { DATA_GENERATION_CHANGED_EVENT } from "./data-refresh-context";
import {
  localNotificationPermission,
  requestLocalNotificationPermission,
  submitFollowNotification,
  type LocalNotificationPermission,
} from "./notifications";

const EMPTY_LIST: FollowListResponse = {
  schema_version: "0.1.0",
  items: [],
  total: 0,
  unread_event_count: 0,
  calendar_exportable_count: 0,
  calendar_omitted_count: 0,
};
const EMPTY_SETTINGS: FollowSettings = {
  schema_version: "0.1.0",
  notifications_opt_in: false,
  notifications_supported: false,
};

export interface FollowController {
  supported: boolean;
  list: FollowListResponse;
  settings: FollowSettings;
  permission: LocalNotificationPermission;
  loading: boolean;
  listStatus: "loading" | "ready" | "error";
  markingRead: boolean;
  changingMatchId: string | null;
  error: Error | null;
  markReadError: Error | null;
  byMatchId: ReadonlyMap<string, FollowedMatch>;
  follow: (matchId: string) => Promise<void>;
  unfollow: (followId: string, matchId?: string) => Promise<void>;
  reload: () => Promise<void>;
  markRead: (eventIds: string[]) => Promise<void>;
  markAllRead: () => Promise<void>;
  enableNotifications: () => Promise<LocalNotificationPermission>;
  disableNotifications: () => Promise<void>;
  removeHistory: () => Promise<void>;
}

export const FollowContext = createContext<FollowController | null>(null);

/** Load the complete active-follow set while preserving the server's global
 * counters. FollowButton and every page-level summary must read this one list;
 * a capped or separately fetched snapshot can mislabel an already-followed
 * fixture after the user changes it elsewhere. */
export async function fetchAllActiveFollows(): Promise<FollowListResponse> {
  const pageSize = 200;
  let offset = 0;
  let latest: FollowListResponse = EMPTY_LIST;
  const items: FollowedMatch[] = [];
  while (true) {
    const page = await fetchFollows("active", 20, pageSize, offset);
    latest = page;
    items.push(...page.items);
    offset += page.items.length;
    if (page.items.length === 0 || offset >= page.total) break;
  }
  return { ...latest, items, total: latest.total };
}

export function useFollowController(backendReady: boolean): FollowController {
  const [list, setList] = useState<FollowListResponse>(EMPTY_LIST);
  const [settings, setSettings] = useState<FollowSettings>(EMPTY_SETTINGS);
  const [permission, setPermission] = useState<LocalNotificationPermission>("unsupported");
  const [loading, setLoading] = useState(false);
  const [listStatus, setListStatus] = useState<FollowController["listStatus"]>(
    backendReady ? "loading" : "ready",
  );
  const [markingRead, setMarkingRead] = useState(false);
  const [changingMatchId, setChangingMatchId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [markReadError, setMarkReadError] = useState<Error | null>(null);
  const reconciling = useRef<Promise<void> | null>(null);
  const markingReadRef = useRef(false);
  const changingRef = useRef(false);

  const reload = useCallback(async () => {
    if (!backendReady) return;
    const nextList = await fetchAllActiveFollows();
    setList(nextList);
    setListStatus("ready");
    try {
      const [nextSettings, nextPermission] = await Promise.all([
        fetchFollowSettings(),
        localNotificationPermission(),
      ]);
      setSettings(nextSettings);
      setPermission(nextPermission);
      if (nextSettings.notifications_opt_in && nextPermission !== "granted") {
        const disabled = await updateFollowSettings(false);
        setSettings(disabled);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    }
  }, [backendReady]);

  const deliverPending = useCallback(async () => {
    if (!backendReady) return;
    const claim = await claimFollowNotifications();
    if (!claim.events.length) return;
    const outcome = document.hasFocus() ? "suppressed_visible" : null;
    if (outcome) {
      await Promise.all(
        claim.events.map((event) => updateFollowNotification(event.event_id, outcome)),
      );
      return;
    }
    const currentPermission = await localNotificationPermission();
    if (currentPermission !== "granted") {
      await Promise.all(
        claim.events.map((event) =>
          updateFollowNotification(event.event_id, "permission_denied"),
        ),
      );
      setPermission(currentPermission);
      setSettings(await updateFollowSettings(false));
      return;
    }
    try {
      submitFollowNotification();
      await Promise.all(
        claim.events.map((event) => updateFollowNotification(event.event_id, "submitted")),
      );
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause);
      await Promise.all(
        claim.events.map((event) =>
          updateFollowNotification(event.event_id, "failed", message),
        ),
      );
    }
  }, [backendReady]);

  const reconcile = useCallback(async () => {
    if (!backendReady || reconciling.current) return reconciling.current ?? Promise.resolve();
    const work = (async () => {
      try {
        setError(null);
        await reconcileFollows();
        await deliverPending();
        await reload();
      } catch (cause) {
        setError(cause instanceof Error ? cause : new Error(String(cause)));
        setListStatus((current) => current === "ready" ? current : "error");
      }
    })();
    reconciling.current = work;
    try {
      await work;
    } finally {
      reconciling.current = null;
    }
  }, [backendReady, deliverPending, reload]);

  useEffect(() => {
    if (!backendReady) return;
    setLoading(true);
    setListStatus("loading");
    void reconcile().finally(() => setLoading(false));
    const onGeneration = () => void reconcile();
    window.addEventListener(DATA_GENERATION_CHANGED_EVENT, onGeneration);
    return () => window.removeEventListener(DATA_GENERATION_CHANGED_EVENT, onGeneration);
  }, [backendReady, reconcile]);

  const follow = useCallback(async (matchId: string) => {
    if (changingRef.current) return;
    changingRef.current = true;
    setChangingMatchId(matchId);
    setError(null);
    let changed = false;
    try {
      await followMatch(matchId);
      changed = true;
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
      if (changed) setListStatus("error");
    } finally {
      changingRef.current = false;
      setChangingMatchId(null);
    }
  }, [reload]);

  const unfollow = useCallback(async (followId: string, matchId?: string) => {
    if (changingRef.current) return;
    changingRef.current = true;
    setChangingMatchId(matchId ?? followId);
    setError(null);
    let changed = false;
    try {
      await unfollowMatch(followId);
      changed = true;
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
      if (changed) setListStatus("error");
    } finally {
      changingRef.current = false;
      setChangingMatchId(null);
    }
  }, [reload]);

  const markAllRead = useCallback(async () => {
    if (markingReadRef.current) return;
    markingReadRef.current = true;
    setMarkingRead(true);
    setError(null);
    setMarkReadError(null);
    try {
      await markFollowEventsRead();
      await reload();
    } catch (cause) {
      const failure = cause instanceof Error ? cause : new Error(String(cause));
      setError(failure);
      setMarkReadError(failure);
    } finally {
      markingReadRef.current = false;
      setMarkingRead(false);
    }
  }, [reload]);

  const markRead = useCallback(async (eventIds: string[]) => {
    if (!eventIds.length || markingReadRef.current) return;
    markingReadRef.current = true;
    setMarkingRead(true);
    setError(null);
    setMarkReadError(null);
    try {
      await markFollowEventsRead(eventIds);
      await reload();
    } catch (cause) {
      const failure = cause instanceof Error ? cause : new Error(String(cause));
      setError(failure);
      setMarkReadError(failure);
    } finally {
      markingReadRef.current = false;
      setMarkingRead(false);
    }
  }, [reload]);

  const enableNotifications = useCallback(async () => {
    const next = await requestLocalNotificationPermission();
    setPermission(next);
    setSettings(await updateFollowSettings(next === "granted"));
    return next;
  }, []);

  const disableNotifications = useCallback(async () => {
    setSettings(await updateFollowSettings(false));
  }, []);

  const removeHistory = useCallback(async () => {
    await removeFollowHistory();
    setList(EMPTY_LIST);
    setSettings(await fetchFollowSettings());
  }, []);

  const byMatchId = useMemo(
    () => new Map(list.items.map((item) => [item.canonical_match_id, item])),
    [list.items],
  );

  return {
    supported: HAS_BACKEND,
    list,
    settings,
    permission,
    loading,
    listStatus,
    markingRead,
    changingMatchId,
    error,
    markReadError,
    byMatchId,
    follow,
    unfollow,
    reload,
    markRead,
    markAllRead,
    enableNotifications,
    disableNotifications,
    removeHistory,
  };
}

export function useFollows(): FollowController {
  const value = useContext(FollowContext);
  if (!value) throw new Error("useFollows must be used inside FollowContext.Provider");
  return value;
}
