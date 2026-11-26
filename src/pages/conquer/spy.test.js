import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Spy from "./spy";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({}) }));
});

const later = new Date(Date.now() + 3600 * 1000).toISOString();
const data = (revealed) => ({
    kingdom: { drones: 1000, spy_attempts: 5, fuel: 1000, completed_projects: [] },
    state: {
        game_config: {},
        reveal_operations: ["spymilitary", "spyshields"],
        reveal_operation_stats: { spymilitary: ["military"], spyshields: ["shields"] },
        pretty_names: {},
    },
    revealed: { revealed: { 2: revealed }, galaxies: {}, revealed_galaxymates: [] },
    kingdoms: { 2: "Other" },
    galaxies_inverted: { 2: "1:1" },
});

const renderSpy = (revealed, operation) => render(
    <MemoryRouter><Spy data={data(revealed)} loading={{}} updateData={jest.fn()} initialKd="2" initialOperation={operation} /></MemoryRouter>
);

test("a reveal of what is already revealed is blocked with the reason, before sending (#155)", () => {
    renderSpy({ military: later }, "spymilitary");
    fireEvent.change(screen.getByLabelText("Drones to send"), { target: { value: "10" } });
    expect(screen.getAllByText("You already have their military revealed").length).toBeGreaterThan(0);
});

test("a reveal of something not revealed is not blocked for that reason", () => {
    renderSpy({ military: later }, "spyshields");
    fireEvent.change(screen.getByLabelText("Drones to send"), { target: { value: "10" } });
    expect(screen.queryByText(/You already have their/)).toBeNull();
});

const repeatData = (recurring = []) => {
    const base = data({});
    return {
        ...base,
        kingdomid: { kd_id: "1" },
        kingdom: { ...base.kingdom, recurring },
        kingdoms: { 1: "Me", 2: "Other" },
        galaxies_inverted: { 1: "1:2", 2: "1:1" },
        state: { ...base.state, game_config: { BASE_DRONES_SIPHON_TIME_MULTIPLIER: 12, BASE_EPOCH_SECONDS: 1800, BASE_MAX_RECURRING_ENTRIES: 50 } },
    };
};
const renderRepeat = (operation, recurring) => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<MemoryRouter><Spy data={repeatData(recurring)} loading={{}} updateData={updateData} initialKd="2" initialOperation={operation} /></MemoryRouter>);
    return updateData;
};

test("Repeat it is offered for a siphon, says what it will do and how to stop it, and asks the server to repeat", async () => {
    renderRepeat("siphonfunds");
    fireEvent.change(screen.getByLabelText("Drones to send"), { target: { value: "250" } });
    expect(screen.getByText(/Send it again by itself once each siphon has run its 6 hours/)).toBeTruthy();

    fireEvent.click(screen.getByLabelText(/^Repeat it/));
    const details = screen.getByTestId("spy-repeat-details");
    expect(details.textContent).toMatch(/sends 25.0% of your drones at home \(250 of your 1,000 now\)/);
    expect(details.textContent).toMatch(/press Stop/);
    expect(screen.getByRole("link", { name: /Repeating tab/ }).getAttribute("href")).toBe("/schedule?tab=repeating");

    fireEvent.click(screen.getByRole("button", { name: "Send spies and repeat" }));
    const sent = authFetch.mock.calls.find(([path]) => path === "api/spy/2");
    expect(JSON.parse(sent[1].body).recurring).toBe(true);
});

test("Repeat it is not offered for a hostile operation other than a siphon", () => {
    renderRepeat("bombhomes");
    expect(screen.queryByLabelText(/^Repeat it/)).toBeNull();
});

test("a repeat already on the target is listed with Stop, and the box says why it can not be ticked again", () => {
    const entry = { id: "a", type: "siphon", target: "2", target_name: "Other", operation: "siphonfunds", drones_pct: 0.25,
        shielded: false, next: "2026-06-01T18:00:00+00:00", runs: 1, fails: 0 };
    renderRepeat("siphonfunds", [entry]);
    expect(screen.getByLabelText(/^Repeat it/).disabled).toBe(true);
    expect(screen.getByText("It already repeats on this kingdom")).toBeTruthy();
    expect(screen.getByText("Repeating on this kingdom")).toBeTruthy();
    expect(screen.getByText(/Ran 1 time$/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    const stopped = authFetch.mock.calls.find(([path]) => path === "api/recurring/cancel");
    expect(JSON.parse(stopped[1].body)).toEqual({ id: "a" });
});
