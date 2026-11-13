import React from "react";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";

import { authFetch } from "../auth";
import { createQueryClient, useGameData, GAME_KEYS, ENDPOINTS, initGlobalData } from "./gameData";

jest.mock("../auth", () => ({ authFetch: jest.fn() }));

const KINGDOM = "api/kingdom";

let responses;

const respond = (value) => Promise.resolve({ json: () => Promise.resolve(value) });

const callsTo = (endpoint) => authFetch.mock.calls.filter(([url]) => url === endpoint).length;

const setup = (initialProps = { logged: true }) => {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, retry: false } });
  const wrapper = ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook((props) => useGameData(props), { wrapper, initialProps });
  return { client, ...hook };
};

beforeEach(() => {
  responses = Object.fromEntries(GAME_KEYS.map((key) => [ENDPOINTS[key], { served: key }]));
  authFetch.mockReset();
  authFetch.mockImplementation((url) => respond(responses[url]));
});

test("fetches nothing and reports everything loading while logged out", () => {
  const { result } = setup({ logged: false });

  expect(authFetch).not.toHaveBeenCalled();
  expect(result.current.data).toEqual(initGlobalData);
  expect(GAME_KEYS.every((key) => result.current.loading[key])).toBe(true);
});

test("loads every key once after login, then stops reporting loading", async () => {
  const { result } = setup();

  expect(result.current.data.kingdom).toEqual({});
  await waitFor(() => expect(GAME_KEYS.every((key) => !result.current.loading[key])).toBe(true));

  GAME_KEYS.forEach((key) => {
    expect(result.current.data[key]).toEqual({ served: key });
    expect(callsTo(ENDPOINTS[key])).toBe(1);
  });
  expect(authFetch).toHaveBeenCalledWith(KINGDOM, { keepalive: true });
});

test("a failed key keeps its empty initial value and stops loading", async () => {
  authFetch.mockImplementation((url) => (url === "api/news" ? Promise.reject(new Error("boom")) : respond(responses[url])));
  const { result } = setup();

  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));
  await waitFor(() => expect(result.current.loading.news).toBe(false));
  expect(result.current.data.news).toEqual([]);
  expect(result.current.data.kingdom).toEqual({ served: "kingdom" });
});

test("updateData runs the mutation first, then refetches only the requested keys", async () => {
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));
  authFetch.mockClear();

  const order = [];
  const mutation = jest.fn(async () => {
    order.push("mutation");
    responses[KINGDOM] = { served: "kingdom", gold: 5 };
  });
  authFetch.mockImplementation((url) => {
    order.push("fetch " + url);
    return respond(responses[url]);
  });

  await act(async () => {
    await result.current.updateData(["kingdom", "pinned"], [mutation]);
  });

  expect(order[0]).toBe("mutation");
  expect(order.slice(1).sort()).toEqual(["fetch api/kingdom", "fetch api/pinned"]);
  expect(result.current.data.kingdom).toEqual({ served: "kingdom", gold: 5 });
  expect(authFetch).toHaveBeenCalledTimes(2);
});

test("keys are marked loading while their mutation is still running", async () => {
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));

  let finishMutation;
  const mutation = () => new Promise((resolve) => (finishMutation = resolve));
  let update;
  act(() => {
    update = result.current.updateData(["kingdom"], [mutation]);
  });

  expect(result.current.loading.kingdom).toBe(true);
  expect(result.current.loading.pinned).toBe(false);

  await act(async () => {
    finishMutation();
    await update;
  });
  expect(result.current.loading.kingdom).toBe(false);
});

test("updateData clears loading and rethrows when the mutation fails", async () => {
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));

  let error;
  await act(async () => {
    await result.current
      .updateData(["kingdom"], [() => Promise.reject(new Error("nope"))])
      .catch((e) => (error = e));
  });

  expect(error.message).toBe("nope");
  expect(result.current.loading.kingdom).toBe(false);
});

test('updateData(["all"]) refetches every key', async () => {
  const { result } = setup();
  await waitFor(() => expect(GAME_KEYS.every((key) => !result.current.loading[key])).toBe(true));
  authFetch.mockClear();

  await act(async () => {
    await result.current.updateData(["all"]);
  });

  expect(authFetch).toHaveBeenCalledTimes(GAME_KEYS.length);
});

test("ignores unknown keys instead of fetching them", async () => {
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));
  authFetch.mockClear();

  await act(async () => {
    await result.current.updateData(["not_a_real_key"]);
  });

  expect(authFetch).not.toHaveBeenCalled();
  expect(warn).toHaveBeenCalled();
  warn.mockRestore();
});

test("a slow response from before a mutation can not overwrite the data from after it", async () => {
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));

  let resolveSlow;
  authFetch.mockImplementationOnce(() => new Promise((resolve) => (resolveSlow = resolve)));
  act(() => {
    result.current.updateData(["kingdom"]);
  });
  await waitFor(() => expect(resolveSlow).toBeDefined());

  responses[KINGDOM] = { served: "after the mutation" };
  await act(async () => {
    await result.current.updateData(["kingdom"]);
  });
  expect(result.current.data.kingdom).toEqual({ served: "after the mutation" });

  await act(async () => {
    resolveSlow({ json: () => Promise.resolve({ served: "stale" }) });
  });
  expect(result.current.data.kingdom).toEqual({ served: "after the mutation" });
});

test("logging out drops all cached data", async () => {
  const { result, rerender } = setup();
  await waitFor(() => expect(result.current.loading.kingdom).toBe(false));
  expect(result.current.data.kingdom).toEqual({ served: "kingdom" });

  rerender({ logged: false });

  await waitFor(() => expect(result.current.data).toEqual(initGlobalData));
  expect(result.current.loading.kingdom).toBe(true);
});

test("refetches what a kingdom timer produced when that timer rolls over", async () => {
  responses[KINGDOM] = { next_resolve: { mobis: "t1", spy_attempt: "s1" } };
  const { result } = setup();
  await waitFor(() => expect(result.current.loading.mobis).toBe(false));
  expect(callsTo("api/mobis")).toBe(1);

  // A timer that did not change refetches nothing.
  responses[KINGDOM] = { next_resolve: { mobis: "t1", spy_attempt: "s2" } };
  await act(async () => {
    await result.current.updateData(["kingdom"]);
  });
  expect(callsTo("api/mobis")).toBe(1);

  responses[KINGDOM] = { next_resolve: { mobis: "t2", spy_attempt: "s2" } };
  await act(async () => {
    await result.current.updateData(["kingdom"]);
  });
  await waitFor(() => expect(callsTo("api/mobis")).toBe(2));
});

test("everything is fetched again the moment a new player's kingdom is created, and again after a reset", async () => {
  responses[ENDPOINTS.kingdomid] = { kd_id: "", created: false };
  const { result } = setup();
  await waitFor(() => expect(GAME_KEYS.every((key) => !result.current.loading[key])).toBe(true));
  expect(callsTo(KINGDOM)).toBe(1);

  responses[ENDPOINTS.kingdomid] = { kd_id: "7", created: true };
  await act(async () => {
    await result.current.updateData(["kingdomid"]);
  });
  await waitFor(() => expect(callsTo(KINGDOM)).toBe(2));
  expect(callsTo(ENDPOINTS.structures)).toBe(2);

  // Reset Kingdom turns it off and on again.
  responses[ENDPOINTS.kingdomid] = { kd_id: "7", created: false };
  await act(async () => {
    await result.current.updateData(["kingdomid"]);
  });
  responses[ENDPOINTS.kingdomid] = { kd_id: "7", created: true };
  await act(async () => {
    await result.current.updateData(["kingdomid"]);
  });
  await waitFor(() => expect(callsTo(KINGDOM)).toBe(3));
});

test("a player who already had a kingdom does not trigger a second fetch of everything", async () => {
  responses[ENDPOINTS.kingdomid] = { kd_id: "7", created: true };
  const { result } = setup();
  await waitFor(() => expect(GAME_KEYS.every((key) => !result.current.loading[key])).toBe(true));
  await act(async () => {
    await result.current.updateData(["kingdomid"]);
  });
  expect(callsTo(KINGDOM)).toBe(1);
});
