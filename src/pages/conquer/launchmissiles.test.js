import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import LaunchMissiles from "./launchmissiles";

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

test("nothing can be launched until a target and a missile are chosen", () => {
    render(<LaunchMissiles data={data()} loading={{}} updateData={jest.fn()} />);
    expect(launch().disabled).toBe(true);
    expect(launch().title).toBe("Choose a target");
});

test("more missiles than you have is refused with the reason", () => {
    render(<LaunchMissiles data={data()} loading={{}} updateData={jest.fn()} initialKd="2" />);
    type("planet_busters-input", "5");
    expect(screen.getAllByText("You only have 4").length).toBeGreaterThan(0);
    expect(launch().disabled).toBe(true);
    type("planet_busters-input", "4");
    expect(launch().disabled).toBe(false);
});
