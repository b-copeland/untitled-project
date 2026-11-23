import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { Notifications, ago } from "./notifications";

const now = Date.now();
const message = { id: 1, received: now, category: "Attack", status: "warning", message: "You were attacked by Realm 7", delay: 60000 };
const info = (id, text) => ({ id, received: now, category: "Projects", status: "info", message: text, delay: 5000 });

beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: jest.fn(() => Promise.resolve()) } });
    window.getSelection = () => ({ toString: () => "" });
});
afterEach(() => jest.useRealTimers());

test("clicking a notification copies its text and says so", async () => {
    render(<Notifications messages={[message]} clear={() => {}} />);

    fireEvent.click(screen.getByText("You were attacked by Realm 7"));

    await waitFor(() => screen.getByText("Copied"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("You were attacked by Realm 7");
});

test("selecting the text by hand is not a click to copy", () => {
    window.getSelection = () => ({ toString: () => "attacked" });
    render(<Notifications messages={[message]} clear={() => {}} />);

    fireEvent.click(screen.getByText("You were attacked by Realm 7"));

    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
});

test("all notifications are in one panel, what needs attention first, the rest behind Show all", () => {
    const messages = [info(5, "fifth"), info(4, "fourth"), info(3, "third"), info(2, "second"), message];
    render(<Notifications messages={messages} clear={() => {}} />);

    expect(screen.getAllByRole("region", { name: "Notifications" })).toHaveLength(1);
    expect(screen.getByText("5, 1 needing attention")).toBeTruthy();
    expect(screen.getAllByRole("listitem")[0].textContent).toMatch(/attacked/);
    expect(screen.queryByText("second")).toBeNull();
    fireEvent.click(screen.getByText("Show all 5"));
    expect(screen.getByText("second")).toBeTruthy();
    expect(screen.getByText("You were attacked by Realm 7")).toBeTruthy();
});

test("one close button clears them all", () => {
    const clear = jest.fn();
    render(<Notifications messages={[info(2, "second"), message]} clear={clear} />);

    fireEvent.click(screen.getByLabelText("Close notifications"));

    expect(clear).toHaveBeenCalled();
});

test("the panel closes itself after a while, but not while something needs attention", () => {
    jest.useFakeTimers();
    const clear = jest.fn();
    const { rerender } = render(<Notifications messages={[info(1, "first")]} clear={clear} />);
    act(() => jest.advanceTimersByTime(9000));
    expect(clear).toHaveBeenCalledTimes(1);

    rerender(<Notifications messages={[{ ...message, received: Date.now() }]} clear={clear} />);
    act(() => jest.advanceTimersByTime(120000));
    expect(clear).toHaveBeenCalledTimes(1);
});

test("how long ago reads in minutes, then hours", () => {
    expect(ago(now, now + 20000)).toBe("just now");
    expect(ago(now, now + 4 * 60000)).toBe("4 min ago");
    expect(ago(now, now + 130 * 60000)).toBe("2 h ago");
});

test("swiping one notification away removes just that one", () => {
    window.PointerEvent = window.PointerEvent || class extends MouseEvent {
        constructor(type, init = {}) { super(type, init); this.pointerType = init.pointerType; this.pointerId = init.pointerId; }
    };
    jest.useFakeTimers();
    const remove = jest.fn();
    render(<Notifications messages={[info(2, "second"), info(1, "first")]} clear={() => {}} remove={remove} />);
    const item = screen.getByText("second").closest("li");
    fireEvent.pointerDown(item, { clientX: 100, clientY: 10, pointerType: "touch", pointerId: 1 });
    fireEvent.pointerMove(item, { clientX: 20, clientY: 10, pointerType: "touch", pointerId: 1 });
    fireEvent.pointerMove(item, { clientX: -150, clientY: 10, pointerType: "touch", pointerId: 1 });
    fireEvent.pointerUp(item, { clientX: -150, clientY: 10, pointerType: "touch", pointerId: 1 });
    act(() => jest.advanceTimersByTime(500));

    expect(remove).toHaveBeenCalledWith(2);
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
});
