import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ShieldsAndSpending from "./shields";

jest.mock("../../components/header", () => ({ __esModule: true, default: () => null }));
jest.mock("../../components/helpbutton", () => ({ __esModule: true, default: () => null }));

const data = {
    kingdom: { stars: 100, shields: { military: 0.1 }, auto_spending_enabled: false,
        auto_spending: { settle: 0.25, structures: 0.25, military: 0.25, engineers: 0.25 }, funding: {} },
    shields: { desc: { military: { max: 0.2, cost: 0.01 } } },
};

test("shields and spending are separate tabs, opening on shields", () => {
    render(<MemoryRouter><ShieldsAndSpending data={data} loading={{}} updateData={jest.fn()} /></MemoryRouter>);

    expect(screen.getByRole("tab", { name: "Shields" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Spy Radar")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Spending" }));
    expect(screen.getByRole("tab", { name: "Spending" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Update Auto Spending:")).toBeTruthy();
});

test("a link to #spending opens on the Spending tab", () => {
    render(<MemoryRouter initialEntries={["/shields#spending"]}><ShieldsAndSpending data={data} loading={{}} updateData={jest.fn()} /></MemoryRouter>);
    expect(screen.getByRole("tab", { name: "Spending" }).getAttribute("aria-selected")).toBe("true");
});
