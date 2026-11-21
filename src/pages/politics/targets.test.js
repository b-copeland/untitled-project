import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import Targets, { actionButtons, empireKingdoms, pointsText, targetFormErrors, warKingdoms } from "./targets";
import { authFetch } from "../../auth";

jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
jest.mock("../conquer/attack.js", () => (props) => <div>Attack planner on {props.initialKd}</div>);
jest.mock("../conquer/spy.js", () => (props) => <div>Spy planner on {props.initialKd} with {props.initialOperation || "no operation"}</div>);
jest.mock("../conquer/launchmissiles.js", () => (props) => <div>Missile planner on {props.initialKd}</div>);

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const actions = [
    { key: "kidnap", name: "Kidnaps", desc: "Kidnap Population", points: [{ measure: "population", name: "civilian", points: 0.01 }] },
    { key: "successful_attacks", name: "Successful Attacks", desc: "Attacks that won", points: [{ measure: "stars", name: "star", points: 1 }] },
    { key: "failed_attacks", name: "Failed Attacks", desc: "Attacks that lost", points: [{ measure: "units", name: "unit destroyed", points: 0.1 }] },
];

const target = {
    target: "5", name: "Target", galaxy: "1:3", at_war: true,
    actions: { kidnap: 2, successful_attacks: 1, failed_attacks: 1 },
    fund_share: 0.1, fund: { stars: 12, money: 3400 },
    points_total: 40, my_points: 10, my_share: 0.25,
    participants: [
        { kd_id: "2", name: "Member", points: 30, share: 0.75, paid: { stars: 0, money: 0 } },
        { kd_id: "1", name: "Emperor", points: 10, share: 0.25, paid: { stars: 0, money: 0 } },
    ],
    intel: { military: "2099-01-01T00:00:00+00:00" }, remains_share: 0.4,
};

const targets = (overrides = {}) => ({
    empire: "e1", is_emperor: false, can_manage: false, delegates: [], max_delegates: 3, max_targets: 2,
    actions, default_fund_share: 0.1, max_fund_share: 0.5, max_multiplier: 5, removed: { 6: "2099-01-01T00:00:00+00:00" }, remark_cooldown_hours: 12,
    max_payout_stars_share: 0.1,
    at_war_with: ["e2"],
    targets: [target], history: [], ...overrides,
});

const data = (overrides = {}) => ({
    empiretargets: targets(),
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Emperor", 2: "Member", 5: "Target", 6: "Other", 7: "Neutral", 8: "Enemy" },
    galaxies_inverted: { 1: "1:1", 2: "1:2", 5: "1:3", 6: "1:3", 7: "1:4", 8: "1:3" },
    empires_inverted: { empires_inverted: { 1: "e1", 2: "e1", 5: "e2", 6: "e2", 7: "e3", 8: "e2" } },
    ...overrides,
});

test("points read per unit of damage, scaled by the multiplier", () => {
    expect(pointsText(actions[0], 2)).toBe("0.02 points a civilian");
    expect(pointsText(actions[1])).toBe("1 point a star");
});

test("both kinds of attack open one Attack button, and sabotage opens Spy on its operation", () => {
    expect(actionButtons(target).map((button) => button.label)).toEqual(["Kidnap", "Attack"]);
});

test("the empire's kingdoms come from the empires list", () => {
    expect(empireKingdoms(data(), "e1")).toEqual(["1", "2"]);
});

test("only kingdoms of an empire at war with yours can be targeted", () => {
    expect(warKingdoms(data(), targets())).toEqual(["5", "6", "8"]);
    expect(warKingdoms(data(), targets({ at_war_with: [] }))).toEqual([]);
});

test("a target out of war says nothing done to it counts", () => {
    render(<Targets data={data({ empiretargets: targets({ targets: [{ ...target, at_war: false }] }) })} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText(/not at war with this kingdom's empire/)).toBeTruthy();
});

test("without a war, no target can be marked", () => {
    render(<Targets data={data({ empiretargets: targets({ can_manage: true, at_war_with: [], targets: [] }) })}
        loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Manage" }));
    expect(screen.getByRole("button", { name: "Mark as a target" }).title).toMatch(/not at war/);
});

test("the form says why it would be refused", () => {
    const base = { fund_share: "10", actions: { kidnap: { on: true, multiplier: "1" } } };
    expect(Object.values(targetFormErrors(base, targets())).filter(Boolean)).toEqual([]);
    expect(targetFormErrors({ ...base, fund_share: "60" }, targets()).fund_share).toBe("At most 50%");
    expect(targetFormErrors({ ...base, actions: { kidnap: { on: true, multiplier: "9" } } }, targets()).kidnap).toBe("At most 5");
    expect(targetFormErrors({ ...base, actions: {} }, targets()).none).toMatch(/at least one/);
});

test("a member sees the target, its fund and the participants, but no leadership controls", () => {
    render(<Targets data={data()} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("Target (1:3)")).toBeTruthy();
    expect(screen.getByText("12 stars, 3,400 money")).toBeTruthy();
    expect(screen.getByText("10 (25.0%)")).toBeTruthy();
    expect(screen.getByText("40.0% to the fund")).toBeTruthy();
    expect(screen.getByText("10.0% of its land")).toBeTruthy();
    expect(screen.getByText("When the target ends")).toBeTruthy();
    expect(screen.getByRole("cell", { name: "Member" })).toBeTruthy();
    expect(screen.queryByText("Pay out the fund")).toBeNull();
    expect(screen.queryByText("Manage")).toBeNull();
    expect(document.body.textContent).not.toMatch(/epoch/i);
});

test("an action button opens its planner on the target", () => {
    render(<Targets data={data()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Kidnap" }));
    expect(screen.getByText("Spy planner on 5 with kidnappopulation")).toBeTruthy();
});

test("there is no pay out button: removing asks first and says the fund is paid out then", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<Targets data={data({ empiretargets: targets({ can_manage: true }) })} loading={{}} updateData={updateData} />);
    expect(screen.queryByText("Pay out the fund")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove target" }));
    expect(screen.getByText(/Its fund \(12 stars and 3,400 money\) is paid out/)).toBeTruthy();
    expect(screen.getByText(/can not be marked again for 12 hours/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(authFetch).toHaveBeenCalledWith("api/empiretargets/5/remove", expect.objectContaining({ method: "POST" }));
    expect(updateData).toHaveBeenCalledWith(["empiretargets", "kingdom"], [expect.any(Function)]);
});

test("the emperor marks a new target with the actions chosen", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<Targets data={data({ empiretargets: targets({ can_manage: true, is_emperor: true, targets: [] }) })}
        loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: "Manage" }));
    const form = screen.getByText("Mark a new target").closest("section");
    const submit = within(form).getByRole("button", { name: "Mark as a target" });
    expect(submit.title).toBe("Choose a kingdom to target");
    expect(screen.getByText("Delegates")).toBeTruthy();
    // Only kingdoms of an empire at war with yours are offered: not your own, not a neutral one.
    fireEvent.keyDown(within(form).getByLabelText("Kingdom"), { key: "ArrowDown" });
    expect(screen.queryByText("Member (1:2)")).toBeNull();
    expect(screen.queryByText("Neutral (1:4)")).toBeNull();
    expect(screen.queryByText("Other (1:3)")).toBeNull();  // removed too recently
    fireEvent.click(screen.getByText("Enemy (1:3)"));
    expect(submit.title).toMatch(/at least one action/);
    fireEvent.click(within(form).getByLabelText("Kidnaps"));
    fireEvent.click(submit);
    expect(authFetch).toHaveBeenCalledWith("api/empiretargets/add", expect.objectContaining({
        body: JSON.stringify({ target: "8", actions: { kidnap: 1 }, fund_share: "10" }),
    }));
});

test("a kingdom outside any empire is told how targets work", () => {
    render(<Targets data={data({ empiretargets: { empire: null } })} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText(/not in an empire/)).toBeTruthy();
});
