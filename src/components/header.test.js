import React from "react";
import { render, screen } from "@testing-library/react";
import Header from "./header";

jest.mock("../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../auth");

// Create React App resets mocks between tests, so the answer is set before each.
beforeEach(() => authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve("2026-01-01T12:00:00Z") })));

const kingdom = { stars: 1234, fuel: 5000.7, population: 99.9, money: 1000000, networth: 77, spy_attempts: 4, generals_available: 2 };

test("it shows the numbers a player checks on every page", () => {
    render(<Header data={{ kingdom }} />);
    ["Stars: 1,234", "Fuel: 5,000", "Pop: 99", "Money: 1,000,000", "Networth: 77", "Spy Attempts: 4", "Generals: 2"]
        .forEach((text) => expect(screen.getByText(text)).toBeTruthy());
});

test("running out of fuel is flagged, with the reason", () => {
    render(<Header data={{ kingdom: { ...kingdom, fuel: 0 } }} />);
    const item = screen.getByText("Fuel: 0").closest(".header-item");
    expect(item.className).toMatch(/header-alert/);
    expect(item.title).toMatch(/penalty/);
    expect(screen.getByText("Money: 1,000,000").closest(".header-item").className).not.toMatch(/header-alert/);
});

test("nothing is shown before the kingdom has loaded", () => {
    const { container } = render(<Header data={{ kingdom: {} }} />);
    expect(container.textContent).toBe("");
});

test("fuel and money carry their net rate per hour in a tooltip, and when a falling stock runs out", () => {
    const withIncome = { ...kingdom, fuel: 1000, income: { fuel: { net: -250 }, money: { net: 600 } } };
    render(<Header data={{ kingdom: withIncome, state: { game_config: { BASE_EPOCH_SECONDS: 1800 } } }} />);
    expect(screen.getByText("Fuel: 1,000").closest(".header-item").title).toBe("-500 fuel per hour; runs out in about 2.0 h");
    expect(screen.getByText("Money: 1,000,000").closest(".header-item").title).toBe("+1,200 income per hour");
});
