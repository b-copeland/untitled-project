import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { Overview } from "./overview";

const data = (kingdom = {}) => ({
    kingdom: {
        money: 5000, fuel: 1000, population: 200, stars: 100, generals_available: 2, auto_spending_enabled: true,
        units: { engineers: 7 }, shields: { military: 0.1 }, siphons: [],
        income: { money: { net: 600 }, fuel: { net: -250 }, population: 10 },
        ...kingdom,
    },
    mobis: {
        maxes: { defense: { current: 4321 }, offense: { current: 1234 } },
        units: { general_0: { return_time: new Date(Date.now() + 2 * 3.6e6).toISOString() } },
        current_hangar_capacity: 50, max_hangar_capacity: 100,
    },
    structures: { current: { homes: 60 }, hour_24: { homes: 10 } },
    news: [{ time: new Date(Date.now() - 3 * 3.6e6).toISOString(), news: "You were attacked by Delta" }],
    state: { game_config: { BASE_EPOCH_SECONDS: 1800 } },
});
const show = (d, openTab = jest.fn()) => render(<MemoryRouter><Overview data={d} openTab={openTab} /></MemoryRouter>);

test("the four cards answer the questions a returning player asks", () => {
    show(data());
    ["Economy", "Military", "Growth", "Threats"].forEach((title) => expect(screen.getByText(title)).toBeTruthy());
    expect(screen.getByText("+1,200")).toBeTruthy();          // money per hour
    expect(screen.getByText("-500")).toBeTruthy();            // fuel per hour
    expect(screen.getByText(/runs out in about 2.0 h/)).toBeTruthy();
    expect(screen.getByText("4,321")).toBeTruthy();           // defense at home
    expect(screen.getByText(/1 general out, the next back in 1h 59m|1 general out, the next back in 2h 00m/)).toBeTruthy();
    expect(screen.getByText("30 stars have nothing on them.")).toBeTruthy();
    expect(screen.getByText(/You were attacked by Delta/)).toBeTruthy();
});

test("the economy card opens the spending tab", () => {
    const openTab = jest.fn();
    show(data(), openTab);
    fireEvent.click(screen.getByRole("button", { name: "Economy" }));
    expect(openTab).toHaveBeenCalledWith("spending");
});

test("nothing before the kingdom has loaded", () => {
    const { container } = show({ ...data(), kingdom: {} });
    expect(container.textContent).toBe("");
});
