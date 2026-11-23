import { renderHook, act } from "@testing-library/react";
import { useNotifications } from "./notifications";

let mockLastMessage = null;
let mockSocketArgs = [];
jest.mock("react-use-websocket", () => (url, options) => {
    mockSocketArgs = [url, options];
    return { sendMessage: jest.fn(), lastMessage: mockLastMessage };
});

const push = (rerender, body) => {
    mockLastMessage = { data: JSON.stringify(body) };
    act(() => rerender());
};

test("a muted kind is not shown, but still refreshes what it names", () => {
    const updateData = jest.fn();
    const { result, rerender } = renderHook(() => useNotifications({ logged: false, session: {}, updateData, muted: ["settles"] }));

    push(rerender, { kind: "settles", message: "Finished settling 3 stars", update: ["kingdom"] });
    expect(result.current.messages).toHaveLength(0);
    expect(updateData).toHaveBeenCalledWith(["kingdom"]);

    push(rerender, { kind: "attacked", message: "You were attacked", status: "warning", update: [] });
    expect(result.current.messages.map((m) => m.message)).toEqual(["You were attacked"]);

    act(() => result.current.remove(result.current.messages[0].id));
    expect(result.current.messages).toHaveLength(0);
});

test("the socket is open only while logged in, and sends the token as soon as it opens", () => {
    const { rerender } = renderHook(({ logged }) => useNotifications({ logged, session: { accessToken: "tok" }, updateData: jest.fn() }),
        { initialProps: { logged: false } });
    expect(mockSocketArgs[0]).toBeNull();

    rerender({ logged: true });
    const [url, options] = mockSocketArgs;
    expect(url).toMatch(/\/ws\/listen$/);
    const send = jest.fn();
    options.onOpen({ target: { send } });
    expect(JSON.parse(send.mock.calls[0][0])).toEqual({ jwt: "tok" });
    expect(options.shouldReconnect()).toBe(true);
    expect(options.reconnectInterval(10)).toBe(60000);
});
