import React from "react";
import { render, screen, act } from "@testing-library/react";
import {
    FlourishLayer, FlourishStage, attackShip, flourishResult, playFlourish, shotDownCount, shotDownMissiles, spyDrone,
} from "./flourish";

const setReducedMotion = (reduce) => {
    window.matchMedia = jest.fn().mockImplementation((query) => ({ matches: reduce && query.includes("reduce"), media: query }));
};

beforeEach(() => {
    jest.useFakeTimers();
    setReducedMotion(false);
});
afterEach(() => {
    jest.useRealTimers();
});

test("an attack's answer plays its effect over the page, and it goes away by itself", () => {
    render(<FlourishLayer enabled />);
    act(() => flourishResult("attack", { status: "success", message: "You won" }));
    expect(screen.getByTestId("flourish").getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByText("Attack won")).toBeTruthy();

    act(() => { jest.advanceTimersByTime(3000); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("a refused request plays nothing", () => {
    render(<FlourishLayer enabled />);
    act(() => flourishResult("attack", { message: "You do not have enough generals" }));
    act(() => flourishResult("spy", { status: "error", message: "Server is busy" }));
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("nothing plays with Effects off or when the device asks to reduce motion", () => {
    const { rerender } = render(<FlourishLayer enabled={false} />);
    act(() => playFlourish({ kind: "spy", outcome: "success" }));
    expect(screen.queryByTestId("flourish")).toBeNull();

    setReducedMotion(true);
    rerender(<FlourishLayer enabled />);
    act(() => playFlourish({ kind: "spy", outcome: "success" }));
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("a tap skips the effect", () => {
    render(<FlourishLayer enabled />);
    act(() => playFlourish({ kind: "spy", outcome: "failure" }));
    expect(screen.getByText("Operation failed")).toBeTruthy();
    act(() => { window.dispatchEvent(new Event("pointerdown")); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("a won attack loses one ship and the rest fly on; a lost one loses them all", () => {
    const after = 3;
    expect([0, 1, 2, 3, 4].map((i) => attackShip(i, after, true).alive)).toEqual([true, true, true, false, true]);
    expect([0, 1, 2, 3, 4].map((i) => attackShip(i, after, false).alive)).toEqual([false, false, false, false, false]);
    // The survivors leave the stage on the right.
    expect(attackShip(0, after, true).x).toBeGreaterThan(320);
});

test("the spy drone gets away when the operation passes and is shot down when it fails", () => {
    expect(spyDrone(1.8, true).alive).toBe(true);
    expect(spyDrone(1.8, true).x).toBeGreaterThan(320);
    expect(spyDrone(1.8, false).alive).toBe(false);
});

test("the missiles shot down follow the share of the damage the shields stopped", () => {
    expect(shotDownCount(0)).toBe(0);
    expect(shotDownCount(undefined)).toBe(0);
    expect(shotDownCount(0.02)).toBe(1);   // any stop shows at least one
    expect(shotDownCount(0.5)).toBe(3);
    expect(shotDownCount(0.98)).toBe(5);   // one still gets through
    expect(shotDownCount(1)).toBe(6);
    expect(shotDownMissiles(2).filter(Boolean)).toHaveLength(2);
    expect(shotDownMissiles(2)[0]).toBe(false);  // spread through the salvo, not the first ones
});

test("the missile caption says whether the shields stopped any", () => {
    const caption = (shieldsStopped) => {
        const { container, unmount } = render(<FlourishStage effect={{ kind: "missiles", outcome: "success", shieldsStopped }} t={2} />);
        const text = container.querySelector(".fl-caption").textContent;
        unmount();
        return text;
    };
    expect(caption(0)).toBe("Missiles struck");
    expect(caption(0.3)).toBe("Shields stopped some");
    expect(caption(1)).toBe("Shields stopped them all");
});

test("the election reveal shows the winning options behind the curtains", () => {
    render(<FlourishStage effect={{ kind: "election", lines: ["Trade: Open markets"] }} t={2} />);
    expect(screen.getByText("The universe has voted")).toBeTruthy();
    expect(screen.getByText("Trade: Open markets")).toBeTruthy();
});

test("every scene draws real numbers all the way through", () => {
    const effects = [
        { kind: "attack", outcome: "success" }, { kind: "attack", outcome: "failure" },
        { kind: "spy", outcome: "success" }, { kind: "spy", outcome: "failure" },
        { kind: "missiles", outcome: "success", shieldsStopped: 0 }, { kind: "missiles", outcome: "success", shieldsStopped: 0.5 },
        { kind: "missiles", outcome: "success", shieldsStopped: 1 }, { kind: "election", lines: ["A: B"] },
    ];
    effects.forEach((effect) => {
        for (let t = 0; t <= 5; t += 0.1) {
            const { container, unmount } = render(<FlourishStage effect={effect} t={t} />);
            expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
            unmount();
        }
    });
});
