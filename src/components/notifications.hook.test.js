import { renderHook, act } from "@testing-library/react";
import { useNotifications } from "./notifications";

let mockLastMessage = null;
jest.mock("react-use-websocket", () => () => ({ sendMessage: jest.fn(), lastMessage: mockLastMessage }));

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
