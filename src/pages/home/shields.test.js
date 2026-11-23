import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ShieldsPage from "./shields";
import { Spending } from "./spending";

jest.mock("../../components/header", () => ({ __esModule: true, default: () => null }));
jest.mock("../../components/helpbutton", () => ({ __esModule: true, default: () => null }));
jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));
const { authFetch } = require("../../auth");

const data = {
    kingdom: { stars: 100, fuel: 500, shields: { military: 0.1, spy: 0.05 }, auto_spending_enabled: false,
        auto_spending: { settle: 0.25, structures: 0.25, military: 0.25, engineers: 0.25 }, funding: {} },
    shields: { desc: { military: { max: 0.1, cost: 0.1 }, spy: { max: 0.2, cost: 0.05 }, spy_radar: { max: 0.2, cost: 0.05 }, missiles: { max: 1, cost: 0.005 } } },
    state: { game_config: { BASE_EPOCH_SECONDS: 3600 } },
};
const runAll = jest.fn();
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
    runAll.mockImplementation((keys, funcs) => funcs.forEach((f) => f()));
});
const lastBody = () => JSON.parse(authFetch.mock.calls[authFetch.mock.calls.length - 1][1].body);
const slider = (label) => screen.getByLabelText(label);

test("the Shields page shows the shields and not auto spending", () => {
    render(<ShieldsPage data={data} loading={{}} updateData={runAll} />);
    expect(screen.getByText("Spy radar")).toBeTruthy();
    expect(screen.queryByText("Auto spending")).toBeNull();
});

test("the shield sliders start where the shields are, stop at each shield's most, and Update sends all four", () => {
    render(<ShieldsPage data={data} loading={{}} updateData={runAll} />);
    expect(slider("Military shields").value).toBe("10");
    expect(slider("Spy shields").value).toBe("5");
    expect(screen.getByRole("button", { name: "Update" }).disabled).toBe(true);

    fireEvent.change(slider("Spy shields"), { target: { value: "50" } });
    expect(slider("Spy shields").value).toBe("20");                       // spy shields go up to 20%
    fireEvent.change(slider("Military shields"), { target: { value: "0" } });
    expect(screen.getByText("100 fuel per hour, from 125")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(lastBody()).toEqual({ military: 0, spy: 20, spy_radar: 0, missiles: 0 });
});

test("the Spending tab shows auto spending and not the shields", () => {
    render(<Spending kingdom={data.kingdom} loading={{}} updateData={runAll} />);
    expect(screen.getByText("Auto spending")).toBeTruthy();
    expect(screen.queryByText("Spy radar")).toBeNull();
});

test("spending shares start at the current split, together stay within 100%, and only the moved ones are sent", () => {
    render(<Spending kingdom={data.kingdom} loading={{}} updateData={runAll} />);
    expect(slider("Settle share").value).toBe("25");
    fireEvent.change(slider("Settle share"), { target: { value: "60" } });
    expect(slider("Settle share").value).toBe("25");                      // the other three already take 75%
    fireEvent.change(slider("Military share"), { target: { value: "0" } });
    fireEvent.change(slider("Settle share"), { target: { value: "40" } });
    expect(screen.getByText("10% of income kept as money")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(lastBody()).toEqual({ settle: 40, structures: "", military: 0, engineers: "" });
});

test("a shield that is rising starts its slider where it is heading and says when it gets there", () => {
    const climbing = {
        ...data,
        kingdom: { ...data.kingdom, shields: { military: 0.02, spy: 0.05 },
            shields_climb: { military: { from: 0, to: 0.08, since: "2026-01-01T10:00:00+00:00" } } },
    };
    render(<ShieldsPage data={climbing} loading={{}} updateData={runAll} />);
    expect(slider("Military shields").value).toBe("8");
    expect(screen.getByText(/Now 2%.*Rising to 8%, reached at/)).toBeTruthy();
    expect(screen.getByText(/rises to its new level over 60 minutes/)).toBeTruthy();
    fireEvent.change(slider("Spy shields"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Update" }));
    expect(lastBody().military).toBe(8);                                  // the climb is sent as it is, not undone
});
