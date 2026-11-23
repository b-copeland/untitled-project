import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Attack from "./attack";
import Spy from "./spy";
import { authFetch } from "../../auth";
import { TOUR_NO_SEND } from "../../components/tour";

// Send attack and Send spies are off while the guided tour runs, so a new player's first attack is not one sent on
// the tour's example target without intel.

let mockRunning = false;
jest.mock("../../components/tour", () => ({
    ...jest.requireActual("../../components/tour"),
    useTour: () => ({ running: mockRunning }),
}));
jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

const answers = {
    "api/attackcontext/2": {
        mine: { defense_now: 100, defense_if_all_sent: 50 },
        estimate: { units: { attack: 10 }, military_bonus: 0, shields: 0 },
        revealed: {},
    },
    "api/autofill/2": { attacker_units: { attack: 5 } },
    "api/calculate/2": { attacker_offense: 10, defender_defense: 100 },
};
beforeEach(() => {
    mockRunning = false;
    authFetch.mockImplementation((url) => Promise.resolve({ json: () => Promise.resolve(answers[url] || {}) }));
});

const data = {
    kingdom: { units: { attack: 50 }, generals_available: 4, drones: 1000, spy_attempts: 5, fuel: 1000, completed_projects: [] },
    mobis: { units_desc: { attack: { offense: 1, defense: 0 } } },
    state: {
        game_config: {},
        pretty_names: { attack: "Attackers" },
        reveal_operations: ["spymilitary"],
        reveal_operation_stats: { spymilitary: ["military"] },
    },
    revealed: { revealed: {}, galaxies: {}, revealed_galaxymates: [] },
    kingdoms: { 2: "Other" },
    galaxies_inverted: { 2: "1:1" },
};

const renderAttack = () => render(
    <MemoryRouter><Attack data={data} loading={{}} updateData={jest.fn()} initialKd="2" /></MemoryRouter>
);
const renderSpy = () => render(
    <MemoryRouter><Spy data={data} loading={{}} updateData={jest.fn()} initialKd="2" initialOperation="spymilitary" /></MemoryRouter>
);

test("Send attack is off while the tour runs, with the reason", async () => {
    mockRunning = true;
    renderAttack();
    const send = await screen.findByRole("button", { name: "Send attack" });
    expect(send).toBeDisabled();
    expect(screen.getByText(TOUR_NO_SEND)).toBeInTheDocument();
});

test("Send attack is not held back by the tour when it is not running", async () => {
    renderAttack();
    await screen.findByRole("button", { name: "Send attack" });
    expect(screen.queryByText(TOUR_NO_SEND)).toBeNull();
});

test("Send spies is off while the tour runs, with the reason", () => {
    mockRunning = true;
    renderSpy();
    fireEvent.change(screen.getByLabelText("Drones to send"), { target: { value: "10" } });
    expect(screen.getByRole("button", { name: "Send spies" })).toBeDisabled();
    expect(screen.getAllByText(TOUR_NO_SEND).length).toBeGreaterThan(0);
});

test("Send spies is not held back by the tour when it is not running", () => {
    renderSpy();
    fireEvent.change(screen.getByLabelText("Drones to send"), { target: { value: "10" } });
    expect(screen.queryByText(TOUR_NO_SEND)).toBeNull();
    expect(screen.getByRole("button", { name: "Send spies" })).toBeEnabled();
});
