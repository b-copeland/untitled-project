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
