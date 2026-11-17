import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ProjectsContent, { projectRows } from "./projects";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const state = {
    project_categories: { economy: "Economy", military: "Military", racial: "Racial" },
    projects: {
        money_bonus: { name: "Money Bonus", desc: "More money", max_bonus: 0.25, category: "economy" },
        big_flexers: { name: "Big Flexers", desc: "Unlocks big flexers", category: "military" },
        warp: { name: "Warp", desc: "Fast", category: "military", requires: ["big_flexers"] },
        gaian_thing: { name: "Gaian Thing", desc: "For Gaians", category: "racial", race: "Gaian" },
        xo_thing: { name: "Xo Thing", desc: "For Xo", category: "racial", race: "Xo" },
    },
};
const data = (overrides = {}) => ({
    state,
    kingdom: {
        race: "Xo", completed_projects: [], auto_assign_projects: false,
        projects_assigned: { money_bonus: 2 }, projects_points: {}, projects_max_points: {}, projects_target: {},
        ...overrides,
    },
    engineers: { current_engineers: 10, engineers_price: 1000 },
    projects: {
        available_engineers: 8,
        current_bonuses: { money_bonus: 0.1 }, max_bonuses: { money_bonus: 0.25 },
        locked: { warp: 'Complete "Big Flexers" first' },
        points: { money_bonus: 50, big_flexers: 25, warp: 0, xo_thing: 0 },
        max_points: { money_bonus: 100, big_flexers: 100, warp: 500, xo_thing: 1000 },
    },
});

test("projects are grouped by category, and another race's projects are not shown", () => {
    const groups = projectRows(state, data().kingdom, data().projects);
    expect(groups.map((group) => group.title)).toEqual(["Economy", "Military", "Racial"]);
    expect(groups[2].rows.map((row) => row.key)).toEqual(["xo_thing"]);
});

test("a locked project says what unlocks it and can not take engineers", () => {
    render(<ProjectsContent data={data()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    expect(screen.getAllByText('Complete "Big Flexers" first').length).toBeGreaterThan(0);
    expect(document.getElementById("warp-assign-input").disabled).toBe(true);
    expect(document.getElementById("big_flexers-assign-input").disabled).toBe(false);
    expect(screen.queryByText("Gaian Thing")).toBeNull();
    expect(screen.getAllByText("Xo Thing").length).toBeGreaterThan(0);
});

test("a continuous project shows its bonus, a one-time project its progress or that it is done", () => {
    render(<ProjectsContent data={data({ completed_projects: ["big_flexers"] })} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    expect(screen.getAllByText("10.0% / 25.0%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
    expect(document.getElementById("big_flexers-assign-input").disabled).toBe(true);
});

test("assigning sends only the projects with a number", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<ProjectsContent data={data()} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    fireEvent.change(document.getElementById("money_bonus-assign-input"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Assign" }));
    expect(authFetch).toHaveBeenCalledWith("api/projects", expect.objectContaining({ body: JSON.stringify({ assign: { money_bonus: "3" } }) }));
});
