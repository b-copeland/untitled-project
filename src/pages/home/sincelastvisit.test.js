import React from "react";
import { MemoryRouter } from "react-router-dom";
import { act, render, screen } from "@testing-library/react";
import { SinceLastVisit } from "./overview";

const HOUR = 3.6e6;
const hoursAgo = (hours) => new Date(Date.now() - hours * HOUR).toISOString();

const summary = (overrides = {}) => ({
    since: hoursAgo(3),
    since_visit: true,
    from: hoursAgo(3),
    changes: { stars: { from: 300, to: 320 }, networth: { from: 1000, to: 900 }, population: { from: 50, to: 50 },
               drones: { from: 0, to: 0 }, engineers: { from: 2, to: 2 } },
    units: { attack: { from: 10, to: 25 }, defense: { from: 8, to: 5 } },
    units_from: hoursAgo(3),
    structures: { mines: { from: 0, to: 4 } },
    structures_from: hoursAgo(3),
    ...overrides,
});
const data = {
    state: { pretty_names: { attack: "Attackers", defense: "Defenders", mines: "Mines" },
             order: { units: ["attack", "defense"], structures: ["homes", "mines"] } },
    news: [
        { time: hoursAgo(1), kind: "attack", news: "Delta attacked you" },
        { time: hoursAgo(2), kind: "spy", news: "Delta spied on you" },
        { time: hoursAgo(5), kind: "attack", news: "An old attack" },
    ],
};

const show = (load, d = data) => render(<MemoryRouter><SinceLastVisit data={d} load={load} /></MemoryRouter>);

test("after three hours away it shows what changed since the last visit", async () => {
    show(() => Promise.resolve(summary()));

    expect(await screen.findByText("Since you were last here (3h ago)")).toBeTruthy();
    expect(screen.getByText("+20")).toBeTruthy();              // stars
    expect(screen.getByText("-100")).toBeTruthy();             // networth
    expect(screen.getByText("Attackers")).toBeTruthy();
    expect(screen.getByText("+15")).toBeTruthy();
    expect(screen.getByText("Defenders")).toBeTruthy();
    expect(screen.getByText("-3")).toBeTruthy();
    expect(screen.getByText("Mines")).toBeTruthy();
    expect(screen.getByText(/Against you: 1 attack, 1 spy operation\./)).toBeTruthy();
    expect(screen.getByText(/Delta attacked you/)).toBeTruthy();
    expect(screen.queryByText(/An old attack/)).toBeNull();
});

test("when the server counts from an hour ago the card says the last hour", async () => {
    show(() => Promise.resolve(summary({ since: hoursAgo(1), since_visit: false })));

    expect(await screen.findByText("The last hour")).toBeTruthy();
    expect(screen.queryByText(/Delta spied on you/)).toBeNull();  // two hours ago: before the window
});

test("showing the tab again asks the server again", async () => {
    const load = jest.fn(() => Promise.resolve(summary()));
    show(load);
    await screen.findByText("Since you were last here (3h ago)");

    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });

    expect(load).toHaveBeenCalledTimes(2);
});

test("a kingdom with no history yet says so", async () => {
    show(() => Promise.resolve(summary({ changes: {}, units: {}, structures: {}, from: null })));
    expect(await screen.findByText(/no history yet/)).toBeTruthy();
});

test("a failed load says it could not load", async () => {
    show(() => Promise.reject(new Error("offline")));
    expect(await screen.findByText("Could not load what changed.")).toBeTruthy();
});

test("nothing changed and nothing happened", async () => {
    const still = summary({ changes: { stars: { from: 300, to: 300 } }, units: {}, structures: {} });
    show(() => Promise.resolve(still), { ...data, news: [] });
    expect(await screen.findByText("Nothing in your kingdom changed.")).toBeTruthy();
    expect(screen.getByText("No attacks, spy operations or missiles against you.")).toBeTruthy();
});
