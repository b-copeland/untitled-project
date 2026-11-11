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

test("more than the silos have room for is refused, counting what is built and building", () => {
    render(<Missiles data={data()} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "6");   // 10 capacity - 4 built - 1 building = room for 5
    expect(screen.getByText("At most 5 missiles")).toBeTruthy();
    expect(build().disabled).toBe(true);
    type("planet-busters-input", "5");
    expect(build().disabled).toBe(false);
});

test("fuel over what you have blocks the button with the reason", () => {
    const poor = data(["star_busters"]);
    poor.kingdom.fuel = 8000;
    render(<Missiles data={poor} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "5");  // 5,000 fuel: fine
    expect(build().disabled).toBe(false);
    type("star-busters-input", "2");    // plus 4,000: 9,000 > 8,000

    expect(build().disabled).toBe(true);
    expect(build().title).toMatch(/Needs 9,000 fuel, you have 8,000/);
});

test("money over what you have blocks the button with the reason", () => {
    const poor = data();
    poor.kingdom.money = 9000;
    render(<Missiles data={poor} loading={{}} updateData={jest.fn()} />);
    type("planet-busters-input", "5");  // 10,000 money > 9,000

    expect(build().disabled).toBe(true);
    expect(build().title).toMatch(/Costs 10,000 money, you have 9,000/);
});
