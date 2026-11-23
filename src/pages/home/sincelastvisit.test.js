import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { SinceLastVisit } from "./overview";
import { resetVisitClock, startVisitClock } from "../../lastVisit";

const HOUR = 3.6e6;
const hoursAgo = (hours) => new Date(Date.now() - hours * HOUR).toISOString();

const summary = {
    from: hoursAgo(3),
    changes: { stars: { from: 300, to: 320 }, networth: { from: 1000, to: 900 }, population: { from: 50, to: 50 },
               drones: { from: 0, to: 0 }, engineers: { from: 2, to: 2 } },
    units: { attack: { from: 10, to: 25 }, defense: { from: 8, to: 5 } },
    units_from: hoursAgo(3),
    structures: { mines: { from: 0, to: 4 } },
    structures_from: hoursAgo(3),
};
const data = {
    state: { pretty_names: { attack: "Attackers", defense: "Defenders", mines: "Mines" },
             order: { units: ["attack", "defense"], structures: ["homes", "mines"] } },
    news: [
        { time: hoursAgo(1), kind: "attack", news: "Delta attacked you" },
        { time: hoursAgo(2), kind: "spy", news: "Delta spied on you" },
        { time: hoursAgo(5), kind: "attack", news: "An old attack" },
    ],
};

function show(load) {
    return render(<MemoryRouter><SinceLastVisit data={data} load={load} /></MemoryRouter>);
}

beforeEach(() => {
    window.localStorage.clear();
    resetVisitClock();
});

test("after three hours away it summarises since the last visit", async () => {
    window.localStorage.setItem("FARSTEEL_LAST_VISIT", hoursAgo(3));
    startVisitClock();
    const load = jest.fn(() => Promise.resolve(summary));
    show(load);

    expect(screen.getByText("Since you were last here (3h ago)")).toBeTruthy();
    expect(await screen.findByText("+20")).toBeTruthy();       // stars
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

test("the last visit read is the one before this page load, not the time just stamped", async () => {
    const before = hoursAgo(2);
    window.localStorage.setItem("FARSTEEL_LAST_VISIT", before);
    startVisitClock();
    const load = jest.fn(() => new Promise(() => {}));
    show(load);

    await waitFor(() => expect(load).toHaveBeenCalledWith(before));
    expect(Date.parse(window.localStorage.getItem("FARSTEEL_LAST_VISIT"))).toBeGreaterThan(Date.parse(before));
});

test("a visit less than an hour ago, or none, shows the last hour", async () => {
    window.localStorage.setItem("FARSTEEL_LAST_VISIT", hoursAgo(0.5));
    startVisitClock();
    const load = jest.fn(() => new Promise(() => {}));
    show(load);

    expect(screen.getByText("The last hour")).toBeTruthy();
    await waitFor(() => expect(load).toHaveBeenCalled());
    expect(Date.now() - Date.parse(load.mock.calls[0][0])).toBeGreaterThanOrEqual(HOUR - 1000);
});

test("a kingdom with no history yet says so", async () => {
    show(() => Promise.resolve({ from: null, changes: {}, units: {}, structures: {} }));
    expect(await screen.findByText(/no history yet/)).toBeTruthy();
});

test("a failed load says it could not load", async () => {
    show(() => Promise.reject(new Error("offline")));
    expect(await screen.findByText("Could not load what changed.")).toBeTruthy();
});

test("nothing changed and nothing happened", async () => {
    const still = { from: hoursAgo(1), changes: { stars: { from: 300, to: 300 } }, units: {}, structures: {} };
    render(<MemoryRouter><SinceLastVisit data={{ ...data, news: [] }} load={() => Promise.resolve(still)} /></MemoryRouter>);
    expect(await screen.findByText("Nothing in your kingdom changed.")).toBeTruthy();
    expect(screen.getByText("No attacks, spy operations or missiles against you.")).toBeTruthy();
});
