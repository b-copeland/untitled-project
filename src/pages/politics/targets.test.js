import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import Targets, { actionButtons, empireKingdoms, pointsText, targetFormErrors } from "./targets";
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
    target: "5", name: "Target", galaxy: "1:3",
    actions: { kidnap: 2, successful_attacks: 1, failed_attacks: 1 },
    fund_share: 0.1, fund: { stars: 12, money: 3400 },
    points_total: 40, my_points: 10, my_share: 0.25,
    participants: [
        { kd_id: "2", name: "Member", points: 30, share: 0.75, paid: { stars: 0, money: 0 } },
        { kd_id: "1", name: "Emperor", points: 10, share: 0.25, paid: { stars: 0, money: 0 } },
    ],
    intel: { military: "2099-01-01T00:00:00+00:00" },
    next_payout_at: null, payout_problem: null,
};

const targets = (overrides = {}) => ({
    empire: "e1", is_emperor: false, can_manage: false, delegates: [], max_delegates: 3, max_targets: 2,
    actions, default_fund_share: 0.1, max_fund_share: 0.5, max_multiplier: 5, payout_cooldown_hours: 0.5,
    targets: [target], history: [], ...overrides,
});

const data = (overrides = {}) => ({
    empiretargets: targets(),
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Emperor", 2: "Member", 5: "Target", 6: "Other" },
    galaxies_inverted: { 1: "1:1", 2: "1:2", 5: "1:3", 6: "1:3" },
    empires_inverted: { empires_inverted: { 1: "e1", 2: "e1" } },
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

test("leadership pays out, and removing asks first and says what happens to the fund", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<Targets data={data({ empiretargets: targets({ can_manage: true }) })} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("button", { name: "Pay out the fund" }));
    expect(authFetch).toHaveBeenCalledWith("api/empiretargets/5/payout", expect.objectContaining({ method: "POST" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove target" }));
    expect(screen.getByText(/Its fund \(12 stars and 3,400 money\) is paid out/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(authFetch).toHaveBeenCalledWith("api/empiretargets/5/remove", expect.objectContaining({ method: "POST" }));
    expect(updateData).toHaveBeenCalledWith(["empiretargets", "kingdom"], [expect.any(Function)]);
});

test("a payout on cooldown is blocked with the reason", () => {
    const later = new Date(Date.now() + 20 * 60000).toISOString();
    render(<Targets data={data({ empiretargets: targets({ can_manage: true, targets: [{ ...target, next_payout_at: later }] }) })}
        loading={{}} updateData={jest.fn()} />);
    const button = screen.getByRole("button", { name: "Pay out the fund" });
    expect(button.disabled).toBe(true);
    expect(button.title).toMatch(/again in 20 min/);
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
    // The empire's own kingdoms are not offered.
    fireEvent.keyDown(within(form).getByLabelText("Kingdom"), { key: "ArrowDown" });
    expect(screen.queryByText("Member (1:2)")).toBeNull();
    fireEvent.click(screen.getByText("Other (1:3)"));
    expect(submit.title).toMatch(/at least one action/);
    fireEvent.click(within(form).getByLabelText("Kidnaps"));
    fireEvent.click(submit);
    expect(authFetch).toHaveBeenCalledWith("api/empiretargets/add", expect.objectContaining({
        body: JSON.stringify({ target: "6", actions: { kidnap: 1 }, fund_share: "10" }),
    }));
});

test("a kingdom outside any empire is told how targets work", () => {
    render(<Targets data={data({ empiretargets: { empire: null } })} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText(/not in an empire/)).toBeTruthy();
});
