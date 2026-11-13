import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Missiles from "./missiles";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));

const desc = {
    planet_busters: { cost: 2000, fuel_cost: 1000 }, star_busters: { cost: 6000, fuel_cost: 2000 }, galaxy_busters: { cost: 15000, fuel_cost: 4000 },
};
const data = (completed = []) => ({
    kingdom: { completed_projects: completed, money: 50000, fuel: 20000 },
    missiles: { capacity: 10, current: { planet_busters: 4 }, building: { planet_busters: 1 }, desc, cost_modifier: 1, build_time: 7200 },
    state: {},
});
const type = (id, value) => fireEvent.change(document.getElementById(id), { target: { value } });
const build = () => screen.getByRole("button", { name: "Build" });

test("locked missiles say what unlocks them and cannot be typed into", () => {
    render(<Missiles data={data()} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText('Research "Star Busters" Project to Unlock')).toBeTruthy();
    expect(document.getElementById("star-busters-input").disabled).toBe(true);
    expect(document.getElementById("planet-busters-input").disabled).toBe(false);
});

test("the slider stops at the room in the silos, counting what is built and building", () => {
    render(<Missiles data={data()} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "6");   // 10 capacity - 4 built - 1 building = room for 5
    expect(document.getElementById("planet-busters-input").value).toBe("5");
    expect(build().disabled).toBe(false);
});

test("the fuel left after the others caps a slider", () => {
    const poor = data(["star_busters"]);
    poor.kingdom.fuel = 8000;
    render(<Missiles data={poor} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "5");  // 5,000 fuel
    type("star-busters-input", "2");    // would be 4,000 more; only 3,000 are left, so one
    expect(document.getElementById("star-busters-input").value).toBe("1");
    expect(build().disabled).toBe(false);
});

test("the money left after the others caps a slider", () => {
    const poor = data();
    poor.kingdom.money = 9000;
    render(<Missiles data={poor} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "5");  // 10,000 money > 9,000: four are affordable
    expect(document.getElementById("planet-busters-input").value).toBe("4");
    expect(build().disabled).toBe(false);
});
