import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Help from "./help";

beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.resolve({}) }));
});

test("help shows one topic at a time and pages through them", () => {
    render(<MemoryRouter><Help /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Guide" }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Status →|Status →/ }));
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
    expect(screen.getAllByRole("heading", { name: "Politics - Cluster" }).length).toBeGreaterThan(0);
    expect(await screen.findByText(/past 2.5%, votes add 80% as much/)).toBeTruthy();
});

test("help opens on the topic for the page it was asked from", () => {
    render(<MemoryRouter><Help scrollTarget="spy" /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Conquer - Spy" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Guide" })).toBeNull();
});
