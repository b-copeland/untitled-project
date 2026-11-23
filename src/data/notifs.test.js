import { markRead } from "./notifs";
import { authFetch } from "../auth";

jest.mock("../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ ok: true })) }));

test("the list is refetched before marking read, up to the total the page had", async () => {
    const calls = [];
    const updateData = jest.fn(async (keys, depFuncs = []) => {
        for (const run of depFuncs) await run();
        calls.push(keys.join(","));
    });

    await markRead(updateData, { news_kingdom: 2, news_kingdom_total: 7 }, ["news_kingdom"], ["news"]);

    expect(calls).toEqual(["news", "notifs"]);
    const body = JSON.parse(authFetch.mock.calls[0][1].body);
    expect(body).toEqual({ categories: ["news_kingdom"], seen: { news_kingdom: 7 } });
});

test("without a total it asks to clear the category", async () => {
    authFetch.mockClear();
    const updateData = jest.fn(async (keys, depFuncs = []) => { for (const run of depFuncs) await run(); });

    await markRead(updateData, { messages: 3 }, ["messages"]);

    expect(JSON.parse(authFetch.mock.calls[0][1].body)).toEqual({ categories: ["messages"], seen: {} });
});
