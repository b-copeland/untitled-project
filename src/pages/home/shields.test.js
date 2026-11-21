import React from "react";
import { render, screen } from "@testing-library/react";
import ShieldsPage from "./shields";
import SpendingPage from "./spending";

jest.mock("../../components/header", () => ({ __esModule: true, default: () => null }));
jest.mock("../../components/helpbutton", () => ({ __esModule: true, default: () => null }));

const data = {
    kingdom: { stars: 100, shields: { military: 0.1 }, auto_spending_enabled: false,
        auto_spending: { settle: 0.25, structures: 0.25, military: 0.25, engineers: 0.25 }, funding: {} },
    shields: { desc: { military: { max: 0.2, cost: 0.01 } } },
};

test("the Shields page shows the shields and not auto spending", () => {
    render(<ShieldsPage data={data} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("Spy Radar")).toBeTruthy();
    expect(screen.queryByText("Update Auto Spending:")).toBeNull();
});

test("the Spending page shows auto spending and not the shields", () => {
    render(<SpendingPage data={data} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("Auto spending")).toBeTruthy();
    expect(screen.queryByText("Spy Radar")).toBeNull();
});
