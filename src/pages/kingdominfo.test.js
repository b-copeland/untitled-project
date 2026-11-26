import React from "react";
import { render, screen, within } from "@testing-library/react";
import KingdomContent from "./kingdominfo";
import { withLastKnown } from "../components/lastknown";

jest.mock("../components/helpbutton", () => () => null);

const state = {
    game_config: { BASE_EPOCH_SECONDS: 3600, LAST_KNOWN_FRESH_EPOCHS: 12, LAST_KNOWN_AGING_EPOCHS: 24 },
    units: { attack: {}, engineers: {} }, pretty_names: { attack: "Attackers" }, order: { units: ["attack", "engineers"] },
};
const hoursAgo = (hours) => new Date(Date.now() - hours * 3.6e6).toISOString();

const view = (info) => {
    const { kingdom, endedOf, categories } = withLastKnown(info);
    return render(<KingdomContent data={{ kingdom, endedOf, lastKnown: categories, kingdoms: { 2: "Delta" },
        galaxies_inverted: { 2: "1:2" }, shields: {}, state, kdId: "2" }} />);
};

test("ended intel fills in, coloured by age; live intel is plain", () => {
    view({
        name: "Delta", race: "Xo", stars: 400, networth: 5000,  // stats live
        last_known: {
            drones: { ended: hoursAgo(5), values: { drones: 1234, spy_attempts: 9 } },
            military: { ended: hoursAgo(15), values: { units: { attack: 300, engineers: 7 }, generals_available: 1, generals_out: [] } },
            kingdom: { ended: hoursAgo(40), values: { stars: 350, money: 8888, fuel: 10, population: 20, networth: 1 } },
        },
    });
    expect(screen.getByText("1,234").className).toContain("last-known-fresh");
    expect(screen.getAllByText("300")[0].className).toContain("last-known-aging");
    expect(screen.getByText("8,888").className).toContain("last-known-stale");
    expect(screen.getByText("8,888").getAttribute("title")).toBe("Last known, 40h ago");
    // Live stars and networth win over the kingdom snapshot's.
    expect(screen.getByText("400").className || "").not.toContain("last-known");
    expect(screen.queryByText("350")).toBeNull();
    // The Kingdom tab says its intel has ended.
    expect(screen.getByText(/are last known, from intel that ended 40h ago/)).toBeTruthy();
});

test("without snapshots nothing is marked", () => {
    view({ name: "Delta", race: "Xo", stars: 400 });
    expect(document.querySelector(".last-known")).toBeNull();
    expect(screen.queryByText(/are last known/)).toBeNull();
});

const production = {
    mobis: { future_1: { attack: 5 }, future_2: { attack: 8 }, queued: { attack: 10 } },
    structures: { future_1: { homes: 2 }, future_2: { homes: 2 }, queued: { homes: 3 } },
    engineers: { future_1: { amount: 0 }, future_2: { amount: 4 }, queued: { amount: 4 } },
    settles: { future_1: { amount: 1 }, future_2: { amount: 1 }, queued: { amount: 6 } },
    missiles: { future_1: {}, future_2: {}, queued: { planet_busters: 2 } },
};
const withHorizons = { ...state, game_config: { ...state.game_config, QUEUE_FORECAST_EPOCHS: [1, 2] } };

test("the production tab shows what each queue delivers by each horizon", () => {
    const { kingdom, endedOf, categories } = withLastKnown({ name: "Delta", race: "Xo", production });
    render(<KingdomContent data={{ kingdom, endedOf, lastKnown: categories, kingdoms: {}, galaxies_inverted: {}, shields: {},
        state: withHorizons, kdId: "2" }} />);
    const tab = within(document.querySelector(".kd-production"));
    const cells = (name) => Array.from(tab.getByRole("row", { name: new RegExp(`^${name}`), hidden: true }).querySelectorAll("td"))
        .map((cell) => cell.textContent);
    expect(cells("Attackers")).toEqual(["Attackers", "5", "8", "10"]);
    expect(cells("Homes")).toEqual(["Homes", "2", "2", "3"]);
    expect(cells("Engineers")).toEqual(["Engineers", "0", "4", "4"]);
    expect(cells("Stars")).toEqual(["Stars", "1", "1", "6"]);
    expect(cells("Planet Busters")).toEqual(["Planet Busters", "0", "0", "2"]);
    expect(tab.getAllByRole("columnheader", { name: "Within 2h", hidden: true }).length).toBe(3);
});

test("without production intel the tab says how to get it", () => {
    view({ name: "Delta", race: "Xo" });
    expect(screen.getByText(/Spy on production to see/)).toBeTruthy();
});
