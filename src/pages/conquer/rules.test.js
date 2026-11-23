import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Reactions, describeRule, ruleProblem, ruleRequest } from "./rules";

jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../../auth");
const runAll = jest.fn();
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
    runAll.mockImplementation((keys, funcs) => funcs.forEach((f) => f()));
});
const lastCall = () => authFetch.mock.calls[authFetch.mock.calls.length - 1];

const rule = {
    id: "r", when: { kind: "attacked", lost_only: true },
    then: { kind: "settings", hours: 12, settings: { shields: { military: 0.1 }, auto_attack_enabled: false } },
    cooldown_hours: 6, state: { fires: 1, last: { time: "2026-06-01T12:00:00+00:00", outcome: "settings switched for 12 hours" }, until: "2026-06-02T00:00:00+00:00" },
};

test("a stored rule reads as a sentence", () => {
    expect(describeRule(rule)).toBe("When I am attacked and it works against me: switch shields Military 10%; auto attack off for 12 hours.");
    expect(describeRule({ when: { kind: "fuel_low", hours: 6 }, then: { kind: "missiles_sender", planet_busters: 0, star_busters: 3, galaxy_busters: 0 } }))
        .toBe("When my fuel will run out within 6 hours: fire 3 star busters at whoever did it.");
});

test("the form says what is missing before it can be sent", () => {
    const base = { when: "attacked", then: "settings", hours: "12", cooldown: "6", use: { shields: false, auto_spending: false, auto_attack_enabled: false, auto_rob_enabled: false }, shields: {}, spending: {} };
    expect(ruleProblem(base)).toBe("Choose at least one setting to switch");
    expect(ruleProblem({ ...base, when: "fuel_low", then: "spy_sender" })).toBe("Low fuel has nobody to react against: switch settings instead");
    expect(ruleProblem({ ...base, then: "spy_sender", drones_pct: "" })).toBe("Send between 1% and 100% of your drones");
    expect(ruleProblem({ ...base, use: { ...base.use, auto_rob_enabled: true } })).toBeNull();
});

test("the request carries only the settings chosen", () => {
    const request = ruleRequest({
        when: "spied", lost_only: false, then: "settings", hours: "4", cooldown: "2",
        use: { shields: true, auto_spending: false, auto_attack_enabled: false, auto_rob_enabled: true },
        shields: { military: "", spy: "20", spy_radar: "", missiles: "" }, spending: {}, auto_rob_enabled: false,
    });
    expect(request).toEqual({
        when: { kind: "spied", lost_only: false },
        then: { kind: "settings", hours: "4", settings: { shields: { spy: "20" }, auto_rob_enabled: false } },
        cooldown_hours: "2",
    });
});

test("the tab lists the rules with what they did and removes one", () => {
    render(<Reactions data={{ kingdom: { rules: [rule] } }} loading={{}} updateData={runAll} />);
    expect(screen.getByText(/Fired 1 times; last .*: settings switched for 12 hours/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(lastCall()[0]).toBe("api/rules/cancel");
    expect(JSON.parse(lastCall()[1].body)).toEqual({ id: "r" });
});
