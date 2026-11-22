import React from "react";
import { render as renderBare, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LaunchMissiles from "./launchmissiles";

const render = (element) => renderBare(<MemoryRouter>{element}</MemoryRouter>);

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
import { authFetch } from "../../auth";
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const data = () => ({
    kingdom: { missiles: { planet_busters: 4, star_busters: 0, galaxy_busters: 0 } },
    missiles: { desc: { planet_busters: { stars_damage: 1, fuel_damage: 2, pop_damage: 3 } } },
    kingdoms: { 2: "Other" },
    galaxies_inverted: { 2: 1 },
});
const type = (id, value) => fireEvent.change(document.getElementById(id), { target: { value } });
const launch = () => screen.getByRole("button", { name: "Launch missiles" });

test("only the target shows until one is chosen, and nothing launches until a missile is chosen", () => {
    const { unmount } = render(<LaunchMissiles data={data()} loading={{}} updateData={jest.fn()} />);
    expect(screen.queryByRole("button", { name: "Launch missiles" })).toBeNull();
    unmount();
    render(<LaunchMissiles data={data()} loading={{}} updateData={jest.fn()} initialKd="2" />);
    expect(launch().disabled).toBe(true);
});

test("a missile slider stops at what you have", () => {
    render(<LaunchMissiles data={data()} loading={{}} updateData={jest.fn()} initialKd="2" />);
    type("planet_busters-input", "5");
    expect(document.getElementById("planet_busters-input").value).toBe("4");
    expect(launch().disabled).toBe(false);
});
