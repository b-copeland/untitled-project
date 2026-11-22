import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ProjectsContent, { projectRows, projectSections } from "./projects";
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
    // Only the Assigned cell says why; the points still show.
    const lockedRow = screen.getAllByText('Complete "Big Flexers" first')[0].closest("tr");
    expect(lockedRow).toHaveTextContent("0 / 500");
    expect(screen.getAllByText('Complete "Big Flexers" first')[0].closest("td").getAttribute("colspan")).not.toBe("2");
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

test("Update sends every project's engineers: the one moved, and the others as they are", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<ProjectsContent data={data()} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    fireEvent.change(document.getElementById("money_bonus-assign-input"), { target: { value: "3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Update" })[0]);
    const [, request] = authFetch.mock.calls.find(([url]) => url === "api/projects");
    const { assign } = JSON.parse(request.body);
    expect(assign.money_bonus).toBe(3);
    expect(Object.keys(assign).sort()).toEqual(Object.keys(state.projects).sort());
});


test("a project's engineers can be moved down to 0", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<ProjectsContent data={data()} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    const slider = document.getElementById("money_bonus-assign-input");
    expect(slider.value).toBe("2");
    fireEvent.change(slider, { target: { value: "0" } });
    expect(slider.value).toBe("0");
    fireEvent.click(screen.getAllByRole("button", { name: "Update" })[0]);
    const [, request] = authFetch.mock.calls.find(([url]) => url === "api/projects");
    expect(JSON.parse(request.body).assign.money_bonus).toBe(0);
});
test("continuous projects are in their own section, one-time projects in theirs by category", () => {
    const sections = projectSections(state, data().kingdom, data().projects);
    expect(sections.map((section) => section.key)).toEqual(["continuous", "one-time"]);
    expect(sections[0].groups.flatMap((group) => group.rows.map((row) => row.key))).toEqual(["money_bonus"]);
    expect(sections[1].groups.map((group) => group.title)).toEqual(["Military", "Racial"]);
    render(<ProjectsContent data={data()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    expect(screen.getAllByText("Continuous Projects").length).toBeGreaterThan(0);
    expect(screen.getAllByText("One-Time Projects").length).toBeGreaterThan(0);
});

test("the (i) button opens the project's description", async () => {
    render(<ProjectsContent data={data()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Assign" }));
    fireEvent.click(screen.getAllByRole("button", { name: "About Money Bonus" })[0]);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("More money");
});

test("when a tick moves the kingdom's project points, the page refetches its bonuses; otherwise it does not", () => {
    const updateData = jest.fn();
    const { rerender } = render(<ProjectsContent data={data({ projects_points: { money_bonus: 50 } })} loading={{}} updateData={updateData} />);
    expect(updateData).not.toHaveBeenCalled();
    rerender(<ProjectsContent data={data({ projects_points: { money_bonus: 50 } })} loading={{}} updateData={updateData} />);
    expect(updateData).not.toHaveBeenCalled();
    rerender(<ProjectsContent data={data({ projects_points: { money_bonus: 51.5 } })} loading={{}} updateData={updateData} />);
    expect(updateData).toHaveBeenCalledTimes(1);
    expect(updateData).toHaveBeenCalledWith(["projects"]);
});
