import React from "react";
import { render, screen, act } from "@testing-library/react";
import {
    ATTACK, FlourishLayer, FlourishStage, SPY, fleetShip, flourishResult, playFlourish, searchlight, shotDownCount,
    shotDownMissiles, spyDrone,
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
    act(() => { flourishResult("attack", { status: "success", message: "You won" }); });
    expect(screen.getByTestId("flourish").getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByText("Attack won")).toBeTruthy();

    act(() => { jest.advanceTimersByTime(ATTACK.seconds * 1000); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("a refused request plays nothing", () => {
    render(<FlourishLayer enabled />);
    act(() => { flourishResult("attack", { message: "You do not have enough generals" }); });
    act(() => { flourishResult("spy", { status: "error", message: "Server is busy" }); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("nothing plays with Effects off or when the device asks to reduce motion", () => {
    const { rerender } = render(<FlourishLayer enabled={false} />);
    act(() => { playFlourish({ kind: "spy", outcome: "success" }); });
    expect(screen.queryByTestId("flourish")).toBeNull();

    setReducedMotion(true);
    rerender(<FlourishLayer enabled />);
    act(() => { playFlourish({ kind: "spy", outcome: "success" }); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

test("a tap skips the effect", () => {
    render(<FlourishLayer enabled />);
    act(() => { playFlourish({ kind: "spy", outcome: "failure" }); });
    expect(screen.getByText("Operation failed")).toBeTruthy();
    act(() => { window.dispatchEvent(new Event("pointerdown")); });
    expect(screen.queryByTestId("flourish")).toBeNull();
});

const fleet = (side, t, won) => [0, 1, 2, 3, 4].map((i) => {
    const { x, y, angle, alive } = fleetShip(side, i, t, won);  // what is on screen, not the planned losses
    return { x, y, angle, alive };
});
const alive = (ships) => ships.map((ship) => ship.alive);

test("an attack opens the same way whatever happens, and reveals the outcome only after the pause", () => {
    for (let t = 0; t < ATTACK.reveal; t += 0.1) {
        expect(fleet("ours", t, true)).toEqual(fleet("ours", t, false));
        expect(fleet("theirs", t, true)).toEqual(fleet("theirs", t, false));
    }
    expect(alive(fleet("ours", ATTACK.reveal, true))).toEqual([true, true, true, true, true]);
    expect(alive(fleet("theirs", ATTACK.reveal, true))).toEqual([true, true, true, true, true]);
});

test("a won attack destroys their fleet for one ship and flies on; a lost one loses ours", () => {
    const end = ATTACK.seconds;
    expect(alive(fleet("ours", end, true))).toEqual([true, true, true, false, true]);
    expect(alive(fleet("theirs", end, true))).toEqual([false, false, false, false, false]);
    expect(fleet("ours", end, true)[0].x).toBeGreaterThan(320);  // off the stage on the right
    expect(alive(fleet("ours", end, false))).toEqual([false, false, false, false, false]);
    expect(alive(fleet("theirs", end, false))).toEqual([true, false, true, true, true]);
});

test("a spy operation opens the same way either way; then the drone is spotted or gets away", () => {
    for (let t = 0; t <= SPY.reveal; t += 0.1) {
        expect(spyDrone(t, true)).toEqual(spyDrone(t, false));
        expect(searchlight(t, true)).toBe(searchlight(t, false));
    }
    expect(searchlight(SPY.reveal + 0.5, false)).toBe(180);  // locked on the drone
    expect(spyDrone(SPY.seconds, true).alive).toBe(true);
    expect(spyDrone(SPY.seconds, true).x).toBeGreaterThan(320);
    expect(spyDrone(SPY.seconds, false).alive).toBe(false);
});

test("the promise settles when the effect ends, is skipped, or does not play", async () => {
    render(<FlourishLayer enabled />);
    let done = false;
    act(() => { playFlourish({ kind: "spy", outcome: "success" }).then(() => { done = true; }); });
    await act(async () => { jest.advanceTimersByTime(1000); });
    expect(done).toBe(false);
    await act(async () => { jest.advanceTimersByTime(SPY.seconds * 1000); });
    expect(done).toBe(true);

    let skipped = false;
    act(() => { playFlourish({ kind: "spy", outcome: "success" }).then(() => { skipped = true; }); });
    await act(async () => { window.dispatchEvent(new Event("pointerdown")); });
    expect(skipped).toBe(true);

    await expect(flourishResult("attack", { message: "refused" })).resolves.toBeUndefined();
});

test("with Effects off the promise settles at once", async () => {
    render(<FlourishLayer enabled={false} />);
    await expect(playFlourish({ kind: "attack", outcome: "success" })).resolves.toBeUndefined();
});

test("the missiles shot down follow the share of the damage the shields stopped", () => {
    expect(shotDownCount(0)).toBe(0);
    expect(shotDownCount(undefined)).toBe(0);
    expect(shotDownCount(0.02)).toBe(1);   // any stop shows at least one
    expect(shotDownCount(0.5)).toBe(3);
    expect(shotDownCount(0.98)).toBe(5);   // one still gets through
    expect(shotDownCount(1)).toBe(6);
    expect(shotDownMissiles(2).filter(Boolean)).toHaveLength(2);
    expect(shotDownMissiles(2)).toEqual([false, false, false, false, true, true]);  // the first hit, the last are stopped
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

test("the shield dome shows whether or not the shields stop anything, so it does not spoil the outcome", () => {
    [0, 0.5, 1].forEach((shieldsStopped) => {
        const { container, unmount } = render(<FlourishStage effect={{ kind: "missiles", outcome: "success", shieldsStopped }} t={1.5} />);
        expect(container.querySelector(".fl-shield")).toBeTruthy();
        unmount();
    });
});
