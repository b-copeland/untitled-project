import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MilitaryContent from "./military";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const unit = (cost, offense, defense) => ({ cost, offense, defense, fuel: 1, hangar_capacity: 1 });
const data = () => ({
    kingdom: { money: 10000, units: { recruits: 50, attack: 5, defense: 0, flex: 0, big_flex: 0, engineers: 3 },
               completed_projects: [], units_target: { attack: 0.5 } },
    mobis: {
        units_desc: { attack: unit(100, 5, 0), defense: unit(100, 0, 5), flex: unit(200, 4, 4), big_flex: unit(500, 8, 8) },
        units: { current_total: { attack: 5, recruits: 50 }, hour_24: {}, current: { recruits: 50 } },
        current_hangar_capacity: 50, max_hangar_capacity: 100, recruit_price: 10, recruit_time: 3600,
        current_available_recruits: 10, max_available_recruits: 10,
    },
    state: { pretty_names: {}, game_config: {} },
});
const show = () => render(<MilitaryContent data={data()} loading={{}} updateData={jest.fn()} />);

test("one table, and the switch changes only what you are doing with it", () => {
    show();
    expect(screen.queryByText("Levy")).toBeNull();
    expect(screen.getByText("To Train")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Allocate" }));
    expect(screen.getByText("New Share")).toBeTruthy();
    expect(screen.getByText("50.0%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Disband" }));
    expect(screen.getByText("To Disband")).toBeTruthy();
    expect(screen.getAllByRole("table")).toHaveLength(1);
});

test("hangar space is shown, and a locked unit says what unlocks it", () => {
    show();
    expect(screen.getByText("50 / 100 (50.0%)")).toBeTruthy();
    expect(screen.getByText('Research "Big Flexers" to unlock')).toBeTruthy();
    expect(document.getElementById("big_flex-train-input").disabled).toBe(true);
});

test("training is refused with the reason before it is sent", () => {
    show();
    const train = () => screen.getByRole("button", { name: "Train units" });
    expect(train().disabled).toBe(true);
    fireEvent.change(document.getElementById("attack-train-input"), { target: { value: "20" } });
    expect(train().disabled).toBe(false);
    fireEvent.change(document.getElementById("attack-train-input"), { target: { value: "60" } });
    expect(train().title).toMatch(/50 recruits/);
});
