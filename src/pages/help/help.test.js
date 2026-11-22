import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Help, { FLAT } from "./help";
import { duration } from "./util";

beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve({}) }));
});

test("help shows one topic at a time and pages through them", () => {
    render(<MemoryRouter><Help /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Guide" }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Status →/ }));
    expect(screen.queryByRole("heading", { name: "Guide" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /← Guide/ }));
    expect(screen.getAllByRole("heading", { name: "Guide" }).length).toBeGreaterThan(0);
});

test("the cluster topic lists the benefits from the state", async () => {
    global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve({
        game_config: { CLUSTER_SIZE: 5, CLUSTER_VOTE_RATE: 0.005, CLUSTER_DECAY_RATE: 0.005 },
        cluster_benefits: { unit_cost: { name: "Cheaper Units", desc: "Units cost less", max: 0.05, thresholds: [[0.5, 0.8]] } },
        order: { cluster_benefits: ["unit_cost"] },
    }) }));
    render(<MemoryRouter><Help scrollTarget="clusterpolitics" /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Cluster politics" }).length).toBeGreaterThan(0);
    expect(await screen.findByText(/past 2.5%, votes add 80% as much/)).toBeTruthy();
});

test("help opens on the topic for the page it was asked from", () => {
    render(<MemoryRouter><Help scrollTarget="spy" /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Spy" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Guide" })).toBeNull();
});

test("durations read in hours or minutes", () => {
    const cfg = { BASE_EPOCH_SECONDS: 1800 };
    expect(duration(16, cfg)).toBe("8 hours");
    expect(duration(2, cfg)).toBe("1 hour");
    expect(duration(0.1, cfg)).toBe("3 minutes");
    expect(duration(undefined, {})).toBe("0 hours");
});

// A state with the shapes the topics read, so each renders its numbers and tables.
const STATE = {
    game_config: {
        BASE_EPOCH_SECONDS: 1800, NETWORTH_VALUES: { stars: 20 }, NETWORTH_POINTS: [10, 5],
        BASE_GENERALS_RETURN_TIME_MULTIPLIER: 24, BASE_REVEAL_DURATION_MULTIPLIER: 16, BASE_MINES_INCOME_PER_EPOCH: 50,
        BASE_AUTO_SPENDING_TIME_MULTIPLIER: 0.1, BASE_MAX_SHARE_CUT: 0.2, CLUSTER_SIZE: 5,
    },
    pretty_names: { stars: "Stars", attack: "Attackers", homes: "Homes", siphonfunds: "Siphon Funds" },
    units: { attack: { cost: 300, offense: 6, defense: 0, hangar_capacity: 1, fuel: 0.5 } },
    projects: { pop_bonus: { name: "Pop Bonus", category: "economy", max_bonus: 0.25, desc: "More population" } },
    missiles: { planet_busters: { cost: 1000, fuel_cost: 100, stars_damage: 1, fuel_damage: 0, pop_damage: 0 } },
    cluster_benefits: {},
    aggro_operations: ["siphonfunds"],
};

test.each(FLAT.map(([id, label, Topic]) => [label, Topic]))("the %s topic shows real time and no placeholders", (label, Topic) => {
    for (const state of [{}, STATE]) {
        const { container, unmount } = render(<MemoryRouter><Topic state={state} /></MemoryRouter>);
        const text = container.textContent;
        expect(text).not.toMatch(/epoch/i);
        expect(text).not.toMatch(/\bseconds\b/i);
        expect(text).not.toMatch(/NaN|undefined|not yet implemented/i);
        unmount();
    }
});
