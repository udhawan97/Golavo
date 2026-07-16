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
  changingMatchId: string | null;
  error: Error | null;
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

export function useFollowController(backendReady: boolean): FollowController {
  const [list, setList] = useState<FollowListResponse>(EMPTY_LIST);
  const [settings, setSettings] = useState<FollowSettings>(EMPTY_SETTINGS);
  const [permission, setPermission] = useState<LocalNotificationPermission>("unsupported");
  const [loading, setLoading] = useState(false);
  const [changingMatchId, setChangingMatchId] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const reconciling = useRef<Promise<void> | null>(null);

  const reload = useCallback(async () => {
    if (!backendReady) return;
    const [nextList, nextSettings, nextPermission] = await Promise.all([
      fetchFollows("active", 20),
      fetchFollowSettings(),
      localNotificationPermission(),
    ]);
    setList(nextList);
    setSettings(nextSettings);
    setPermission(nextPermission);
    if (nextSettings.notifications_opt_in && nextPermission !== "granted") {
      const disabled = await updateFollowSettings(false);
      setSettings(disabled);
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
    void reconcile().finally(() => setLoading(false));
    const onGeneration = () => void reconcile();
    window.addEventListener(DATA_GENERATION_CHANGED_EVENT, onGeneration);
    return () => window.removeEventListener(DATA_GENERATION_CHANGED_EVENT, onGeneration);
  }, [backendReady, reconcile]);

  const follow = useCallback(async (matchId: string) => {
    setChangingMatchId(matchId);
    setError(null);
    try {
      await followMatch(matchId);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setChangingMatchId(null);
    }
  }, [reload]);

  const unfollow = useCallback(async (followId: string, matchId?: string) => {
    setChangingMatchId(matchId ?? followId);
    setError(null);
    try {
      await unfollowMatch(followId);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error(String(cause)));
    } finally {
      setChangingMatchId(null);
    }
  }, [reload]);

  const markAllRead = useCallback(async () => {
    await markFollowEventsRead();
    await reload();
  }, [reload]);

  const markRead = useCallback(async (eventIds: string[]) => {
    if (!eventIds.length) return;
    await markFollowEventsRead(eventIds);
    await reload();
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
    changingMatchId,
    error,
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
