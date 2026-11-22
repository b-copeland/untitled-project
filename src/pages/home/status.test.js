import React from "react";
import { render, screen, within } from "@testing-library/react";
import { Military, Structures, horizonLabel } from "./status";

jest.mock("../../components/helpbutton", () => () => null);

const state = (epochSeconds) => ({
    game_config: { BASE_EPOCH_SECONDS: epochSeconds, QUEUE_FORECAST_EPOCHS: [2, 4, 8, 16, 48] },
    pretty_names: { attack: "Attackers" },
    units: { attack: {} },
});

test("column headings follow the epoch length", () => {
    expect([2, 4, 8, 16, 48].map((n) => horizonLabel(n, { BASE_EPOCH_SECONDS: 1800 }))).toEqual(["1h", "2h", "4h", "8h", "24h"]);
    expect([2, 4, 8, 16, 48].map((n) => horizonLabel(n, { BASE_EPOCH_SECONDS: 600 }))).toEqual(["20m", "40m", "1.3h", "2.7h", "8h"]);
});

test("the structures table adds what the queue holds by each horizon", () => {
    const structures = {
        current: { homes: 10 },
        future_2: { homes: 1 }, future_4: { homes: 1 }, future_8: { homes: 3 }, future_16: { homes: 3 }, future_48: { homes: 7 },
        queued: { homes: 7 },
    };
    render(<Structures structures={structures} kingdom={{ stars: 100 }} state={state(3600)} />);
    const [counts] = screen.getAllByRole("row", { name: /Homes/ });
    expect(within(counts).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Homes", "10", "11", "11", "13", "13", "17"]);
    expect(screen.getAllByRole("columnheader", { name: "48h" }).length).toBe(2);
});

test("the mobilization table uses the same horizons", () => {
    const mobis = {
        units: { current: { attack: 5 }, current_total: { attack: 5 }, future_2: { attack: 2 }, future_48: { attack: 4 }, queued: { attack: 4 } },
        maxes: { offense: { current: 50, current_total: 50, future_2: 20 }, defense: { current: 0, current_total: 0 } },
    };
    render(<Military mobis={mobis} state={state(1800)} />);
    const attackers = screen.getAllByRole("row", { name: /Attackers/ }).pop();
    expect(within(attackers).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["Attackers", "5", "7", "5", "5", "5", "9"]);
    const offense = screen.getAllByRole("row", { name: /Max offense/ }).pop();
    expect(within(offense).getAllByRole("cell")[2].textContent).toBe("70");
});
