import React, { useState } from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ResultToasts } from "./results";
import { swipeDismisses } from "./swipe";

// jsdom has no PointerEvent: a mouse event with the pointer's type and id is enough here.
beforeAll(() => {
    window.PointerEvent = class extends MouseEvent {
        constructor(type, init = {}) {
            super(type, init);
            this.pointerType = init.pointerType;
            this.pointerId = init.pointerId;
        }
    };
});
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

function Page() {
    const [results, setResults] = useState([{ message: "Not enough money" }]);
    return <ResultToasts title="Settle" results={results} setResults={setResults} />;
}

const swipe = (element, dx, { pointerType = "touch", dy = 0 } = {}) => {
    fireEvent.pointerDown(element, { clientX: 100, clientY: 100, pointerType, pointerId: 1 });
    fireEvent.pointerMove(element, { clientX: 100 + dx / 2, clientY: 100 + dy / 2, pointerType, pointerId: 1 });
    fireEvent.pointerMove(element, { clientX: 100 + dx, clientY: 100 + dy, pointerType, pointerId: 1 });
    fireEvent.pointerUp(element, { clientX: 100 + dx, clientY: 100 + dy, pointerType, pointerId: 1 });
    act(() => jest.advanceTimersByTime(500));
};

test("far enough, or a quick flick, either way, dismisses; a nudge does not", () => {
    expect(swipeDismisses(120, 300, 1000)).toBe(true);
    expect(swipeDismisses(-120, 300, 1000)).toBe(true);
    expect(swipeDismisses(40, 300, 50)).toBe(true);
    expect(swipeDismisses(40, 300, 1000)).toBe(false);
    expect(swipeDismisses(10, 300, 5)).toBe(false);
});

test("a toast swiped sideways, left or right, closes", () => {
    const { unmount } = render(<Page />);
    swipe(screen.getByRole("alert"), 200);
    expect(screen.queryByText("Not enough money")).toBeNull();
    unmount();

    render(<Page />);
    swipe(screen.getByRole("alert"), -200);
    expect(screen.queryByText("Not enough money")).toBeNull();
});

test("a short swipe, a scroll, or a mouse drag leaves the toast where it is", () => {
    render(<Page />);
    swipe(screen.getByRole("alert"), 20);
    swipe(screen.getByRole("alert"), 30, { dy: 200 });
    swipe(screen.getByRole("alert"), 250, { pointerType: "mouse" });
    expect(screen.getByText("Not enough money")).toBeTruthy();
});
