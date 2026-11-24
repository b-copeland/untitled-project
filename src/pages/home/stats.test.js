import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { KingdomStats, formatStat } from "./stats";
import { authFetch } from "../../auth";

jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

const answer = {
    sections: [
        { title: "Military", rows: [
            { key: "total_offense", label: "Total offense", value: 12345.6, format: "number", tip: "Every unit" },
            { key: "total_offense_per_star", label: "Per star", value: 12.3456, format: "decimal", tip: null },
        ] },
        { title: "Economy", rows: [
            { key: "income_structures_share", label: "Stars with homes or mines", value: 0.7, format: "percent", tip: null },
            { key: "siphons_per_drone_factory", label: "Siphons per drone factory", value: null, format: "decimal", tip: null },
        ] },
    ],
};

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ status: 200, json: () => Promise.resolve(answer) }));
});

const renderStats = () => render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <KingdomStats />
    </QueryClientProvider>,
);

test("figures are written as the server says: whole numbers, decimals, percents, hours, and -- for none", () => {
    expect(formatStat(12345.6, "number")).toBe("12,345");
    expect(formatStat(12.3456, "decimal")).toBe("12.35");
    expect(formatStat(1234.5, "decimal")).toBe("1,235");
    expect(formatStat(0.7, "percent")).toBe("70.0%");
    expect(formatStat(3.5, "hours")).toBe("3h 30m");
    expect(formatStat(null, "decimal")).toBe("--");
});

test("the tab shows each section the server sends, with each row's tip on its label (#239)", async () => {
    renderStats();
    expect(await screen.findByText("Military")).toBeTruthy();
    expect(authFetch).toHaveBeenCalledWith("api/kingdomstats");
    expect(screen.getByText("Economy")).toBeTruthy();
    expect(screen.getByText("Total offense").getAttribute("title")).toBe("Every unit");
    expect(screen.getByText("12,345")).toBeTruthy();
    expect(screen.getByText("70.0%")).toBeTruthy();
    expect(screen.getByText("--")).toBeTruthy();
});
