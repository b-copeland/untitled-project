import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { QueryClient, useQueries, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "../auth";

/**
 * Server state for the game, backed by TanStack Query.
 *
 * Every endpoint is its own query (['game', key]), so keys are fetched in parallel, deduplicated, retried, and a fresh
 * fetch always supersedes an older in-flight one. `useGameData` exposes the same `data` / `loading` / `updateData`
 * contract that the pages have always used, so pages can move to `useQuery` one at a time.
 */

export const ENDPOINTS = {
  kingdomid: "api/kingdomid",
  kingdom: "api/kingdom",
  state: "api/state",
  shields: "api/shields",
  kingdoms: "api/kingdoms",
  galaxies: "api/galaxies",
  galaxies_inverted: "api/galaxies_inverted",
  siphonsout: "api/siphonsout",
  empires: "api/empires",
  empires_inverted: "api/empires_inverted",
  empirepolitics: "api/empirepolitics",
  news: "api/news",
  galaxynews: "api/galaxynews",
  empirenews: "api/empirenews",
  universenews: "api/universenews",
  settle: "api/settle",
  structures: "api/structures",
  mobis: "api/mobis",
  missiles: "api/missiles",
  engineers: "api/engineers",
  projects: "api/projects",
  revealed: "api/revealed",
  shared: "api/shared",
  pinned: "api/pinned",
  galaxypolitics: "api/galaxypolitics",
  universepolitics: "api/universepolitics",
  attackhistory: "api/attackhistory",
  spyhistory: "api/spyhistory",
  missilehistory: "api/missilehistory",
  messages: "api/messages",
  scores: "api/scores",
  notifs: "api/notifs",
};

export const GAME_KEYS = Object.keys(ENDPOINTS);

/** What a key holds before its first successful fetch. */
export const initGlobalData = {
  kingdomid: {},
  kingdom: {},
  state: {},
  shields: {},
  kingdoms: {},
  galaxies: {},
  galaxies_inverted: {},
  siphonsout: [],
  empires: {},
  empires_inverted: {},
  empirepolitics: {},
  news: [],
  settle: {},
  structures: {},
  mobis: {},
  missiles: {},
  engineers: {},
  projects: {},
  revealed: {},
  shared: {},
  pinned: [],
  galaxypolitics: {},
  universepolitics: {},
  attackhistory: [],
  spyhistory: [],
  missilehistory: [],
  galaxynews: [],
  empirenews: [],
  universenews: [],
  messages: [],
  scores: {},
  notifs: {},
};

/** When a `kingdom.next_resolve` timer changes, these keys hold the data it produced. */
export const RESOLVE_KEYS_MAP = {
  generals: ["mobis"],
  spy_attempt: [],
  settles: ["settle", "structures"],
  mobis: ["mobis"],
  missiles: ["missiles"],
  engineers: ["engineers"],
  structures: ["structures"],
  revealed: ["revealed"],
  shared: ["shared"],
  auto_spending: ["kingdom", "settle", "structures", "mobis", "engineers"],
};

export const KINGDOM_POLL_MS = 10 * 1000;
export const SCORES_POLL_MS = 60 * 1000;
const POLL_MS = {
  kingdom: KINGDOM_POLL_MS,
  notifs: KINGDOM_POLL_MS,
  scores: SCORES_POLL_MS,
};

export const gameQueryKey = (key) => ["game", key];

// The API reports failures as a JSON body, which the app has always stored as the key's data, so keep doing that.
const fetchGameKey = (key) => authFetch(ENDPOINTS[key], { keepalive: true }).then((r) => r.json());

export const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        // Data only changes through explicit invalidation (user actions, websocket pushes, polling).
        staleTime: Infinity,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });

// Defined at module level so `useQueries` can memoize the combined result.
const combineResults = (results) => {
  const data = {};
  const fetching = {};
  GAME_KEYS.forEach((key, i) => {
    const result = results[i];
    data[key] = result.data === undefined ? initGlobalData[key] : result.data;
    // Pending covers "not fetched yet", including while logged out.
    fetching[key] = result.isPending || result.isFetching;
  });
  return { data, fetching };
};

/**
 * @param {{logged: boolean}} options
 * @returns {{data: object, loading: object, updateData: Function}}
 *   - `data[key]`: the latest value, or the empty initial value until it loads
 *   - `loading[key]`: true until first load, and while the key refreshes
 *   - `updateData(keys, depFuncs)`: await each `depFunc` (the mutation), then refetch `keys` (`"all"` for everything)
 */
export function useGameData({ logged }) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState({});

  const { data, fetching } = useQueries({
    queries: GAME_KEYS.map((key) => {
      const pollMs = POLL_MS[key];
      return {
        queryKey: gameQueryKey(key),
        queryFn: () => fetchGameKey(key),
        enabled: logged,
        ...(pollMs && {
          // Pauses while the tab is hidden, and catches up when it is shown again.
          refetchInterval:
            key === "scores"
              ? pollMs
              : // A kingdom that has not been created yet has nothing to poll.
                () => (queryClient.getQueryData(gameQueryKey("kingdomid"))?.created !== false ? pollMs : false),
          staleTime: pollMs,
          refetchOnWindowFocus: true,
        }),
      };
    }),
    combine: combineResults,
  });

  const updateData = useCallback(
    async (keys, depFuncs = []) => {
      const wanted = keys.includes("all") ? GAME_KEYS : keys;
      const loadKeys = [...new Set(wanted)].filter((key) => {
        if (key in ENDPOINTS) return true;
        console.warn("updateData: unknown key " + key);
        return false;
      });
      const mark = (delta) =>
        setPending((prev) => {
          const next = { ...prev };
          loadKeys.forEach((key) => {
            next[key] = (next[key] || 0) + delta;
          });
          return next;
        });

      mark(1);
      try {
        for (const depFunc of depFuncs) {
          await depFunc();
        }
        // Invalidating (rather than fetching directly) cancels any older in-flight fetch of the same key, so a slow
        // response from before the mutation can never overwrite the data from after it.
        await Promise.all(loadKeys.map((key) => queryClient.invalidateQueries({ queryKey: gameQueryKey(key) })));
      } finally {
        mark(-1);
      }
    },
    [queryClient]
  );

  // Drop everything when the session ends (logout, or an expired token), so the next user never sees stale data.
  useEffect(() => {
    if (!logged) {
      queryClient.resetQueries({ queryKey: ["game"] });
    }
  }, [logged, queryClient]);

  // When a kingdom timer rolls over, the thing it produced (units, structures, ...) changed, so refetch it.
  const nextResolve = data.kingdom.next_resolve;
  const lastResolve = useRef(null);
  useEffect(() => {
    if (!nextResolve) {
      lastResolve.current = null;
      return;
    }
    const previous = lastResolve.current;
    lastResolve.current = nextResolve;
    if (!previous) {
      return;
    }
    const keys = new Set();
    Object.keys(previous)
      .filter((resolve) => previous[resolve] !== nextResolve[resolve])
      .forEach((resolve) => (RESOLVE_KEYS_MAP[resolve] || []).forEach((key) => keys.add(key)));
    if (keys.size > 0) {
      updateData([...keys]);
    }
  }, [nextResolve, updateData]);

  const loading = useMemo(() => {
    const result = {};
    GAME_KEYS.forEach((key) => {
      result[key] = fetching[key] || (pending[key] || 0) > 0;
    });
    return result;
  }, [fetching, pending]);

  return { data, loading, updateData };
}
