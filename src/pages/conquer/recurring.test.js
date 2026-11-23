import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Repeating, recurringProblems } from "./recurring";

jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));
const { authFetch } = require("../../auth");

const data = {
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Me", 2: "Them" },
    galaxies_inverted: { 1: "1:1", 2: "1:2" },
    state: { game_config: { BASE_MAX_SHARE_CUT: 0.2, BASE_DRONES_SIPHON_TIME_MULTIPLIER: 12, BASE_EPOCH_SECONDS: 1800 } },
    kingdom: {
        recurring: [{
            id: "a", type: "siphon", target: "2", target_name: "Them", operation: "siphonfunds", drones_pct: 0.5,
            shielded: false, next: "2026-06-01T18:00:00+00:00", runs: 2, fails: 0,
            last: { time: "2026-06-01T12:00:00+00:00", status: "success", message: "Success!" },
        }],
    },
};
const runAll = jest.fn();
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
    runAll.mockImplementation((keys, funcs) => funcs.forEach((f) => f()));
});

test("a repeating request needs a target, drones, and an operation for intel", () => {
    const base = { type: "siphon", target: "2", operation: null, drones_pct: "50", stop_after_fails: "3", until: "" };
    expect(recurringProblems(base, "1", 20)).toEqual([]);
    expect(recurringProblems({ ...base, target: null }, "1", 20)[0]).toBe("Choose a target");
    expect(recurringProblems({ ...base, target: "1" }, "1", 20)[0]).toBe("You can not spy on yourself");
    expect(recurringProblems({ ...base, type: "intel" }, "1", 20)[0]).toBe("Choose an operation");
    expect(recurringProblems({ ...base, drones_pct: "0" }, "1", 20)[0]).toBe("Send between 1% and 100% of your drones");
    expect(recurringProblems({ ...base, type: "intel", operation: "spykingdom", share_to_galaxy: true, cut: "30" }, "1", 20)[0]).toBe("The cut is 0% to 20%");
});

test("the Repeating tab lists what repeats, with what it did last, and stops one", () => {
    render(<Repeating data={data} loading={{}} updateData={runAll} />);
    expect(screen.getByText("Siphon funds on Them")).toBeTruthy();
    expect(screen.getByText(/Ran 2 times; last .*: Worked\. Success!/)).toBeTruthy();
    expect(screen.getByText(/once its last siphon has run its 6 hours/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    const [path, init] = authFetch.mock.calls[authFetch.mock.calls.length - 1];
    expect(path).toBe("api/recurring/cancel");
    expect(JSON.parse(init.body)).toEqual({ id: "a" });
});

test("the add button stays blocked until the request is complete", () => {
    render(<Repeating data={data} loading={{}} updateData={runAll} />);
    expect(screen.getByRole("button", { name: "Repeat it" }).disabled).toBe(true);
    expect(screen.getByText("Choose a target")).toBeTruthy();
});
