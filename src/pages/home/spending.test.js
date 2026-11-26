import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { Spending, moveProblem } from "./spending";

jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../../auth");
beforeEach(() => authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "Moved" }) })));

const kingdom = (overrides = {}) => ({
    money: 1000, auto_spending_enabled: true,
    auto_spending: { settle: 0.1, structures: 0.1, military: 0.1, engineers: 0 },
    funding: { settle: 100, structures: 200, military: 300, engineers: 0 },
    ...overrides,
});

test("a move needs two places, something to move and auto spending on to fill a category", () => {
    const kd = kingdom();
    expect(moveProblem({ from: "military", to: "money", amount: "300", kingdom: kd })).toBeNull();
    expect(moveProblem({ from: "military", to: "money", amount: "301", kingdom: kd })).toBe("There is only 300 to move");
    expect(moveProblem({ from: "money", to: "money", amount: "1", kingdom: kd })).toBe("Choose two different places");
    expect(moveProblem({ from: "engineers", to: "money", amount: "1", kingdom: kd })).toBe("There is nothing to move");
    expect(moveProblem({ from: "money", to: "settle", amount: "1", kingdom: kingdom({ auto_spending_enabled: false }) }))
        .toMatch(/Turn auto spending on first/);
    expect(moveProblem({ from: "settle", to: "money", amount: "1", kingdom: kingdom({ auto_spending_enabled: false }) })).toBeNull();
});

test("the Move form sends from, to and the amount", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<Spending kingdom={kingdom()} loading={{}} updateData={updateData} />);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "money" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "structures" } });
    fireEvent.change(screen.getByRole("textbox", { name: /Amount/ }), { target: { value: "250" } });
    fireEvent.click(screen.getByRole("button", { name: "Move" }));
    const sent = authFetch.mock.calls.find(([path]) => path === "api/funding/move");
    expect(JSON.parse(sent[1].body)).toEqual({ from: "money", to: "structures", amount: 250 });
});
