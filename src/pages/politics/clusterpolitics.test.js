import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import ClusterPolitics, { benefitsOf, leadsGalaxy } from "./clusterpolitics";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const cluster = {
    cluster: "1",
    galaxy: "1:1",
    galaxies: [
        { id: "1:1", kingdoms: 4, empire: "0", vote: "unit_cost" },
        { id: "1:2", kingdoms: 3, empire: null, vote: null },
    ],
    // Keys arrive sorted; ``order`` is the game's order.
    benefits: {
        drone_production: { name: "Drone Production", desc: "More drones", max: 0.15, level: 0.5, value: 0.075, rate_per_epoch: 0.0003, votes: 0 },
        settle_cost: { name: "Cheaper Settling", desc: "Cheaper stars", max: 0.1, level: 0, value: 0, rate_per_epoch: 0, votes: 0 },
        unit_cost: { name: "Cheaper Units", desc: "Cheaper units", max: 0.05, level: 0.2, value: 0.01, rate_per_epoch: -0.00025, votes: 1 },
    },
    order: ["drone_production", "unit_cost", "settle_cost"],
    alignment: 0.5,
    vote_gain_per_epoch: 0.005,
    decay_per_epoch: 0.005,
};

const data = (overrides = {}) => ({
    cluster,
    empires: { 0: { name: "The Empire" } },
    galaxypolitics: { leader: "7" },
    kingdomid: { kd_id: "7" },
    state: { game_config: { BASE_EPOCH_SECONDS: 1800 } },
    ...overrides,
});

test("benefits are listed in the game's order", () => {
    expect(benefitsOf(cluster).map((benefit) => benefit.key)).toEqual(["drone_production", "unit_cost", "settle_cost"]);
});

test("only the galaxy leader leads", () => {
    expect(leadsGalaxy(data())).toBe(true);
    expect(leadsGalaxy(data({ kingdomid: { kd_id: "8" } }))).toBe(false);
    expect(leadsGalaxy(data({ galaxypolitics: { leader: "" }, kingdomid: { kd_id: "" } }))).toBe(false);
});

test("the benefits show their level, their change and their votes", () => {
    render(<ClusterPolitics data={data()} loading={{}} updateData={jest.fn()} />);
    const rowOf = (name) => screen.getAllByText(name).find((element) => element.tagName === "STRONG").closest("tr");
    expect(within(rowOf("Cheaper Units")).getByText("1.00% of 5%")).toBeTruthy();
    // Per hour, not per epoch: the server's -0.00025 per half-hour epoch is -0.05% an hour of the max.
    expect(within(rowOf("Cheaper Units")).getByText("-0.050%")).toBeTruthy();
    expect(screen.getByText("Per hour")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/epoch/i);
    expect(within(rowOf("Cheaper Settling")).getByText("Holding")).toBeTruthy();
    expect(screen.getByText("Cheaper Units", { selector: "dd" })).toBeTruthy();  // your galaxy votes for it
});

test("a leader changes the galaxy's vote", () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<ClusterPolitics data={data()} loading={{}} updateData={updateData} />);
    const vote = () => screen.getByRole("button", { name: /Vote|Withdraw vote/ });
    expect(vote().disabled).toBe(true);  // already its vote
    fireEvent.change(screen.getByLabelText("Your galaxy votes for"), { target: { value: "drone_production" } });
    expect(vote().disabled).toBe(false);
    fireEvent.click(vote());
    expect(updateData).toHaveBeenCalledWith(["cluster"], [expect.any(Function)]);
    expect(authFetch).toHaveBeenCalledWith("api/cluster/vote", expect.objectContaining({
        method: "POST", body: JSON.stringify({ benefit: "drone_production" }),
    }));
});

test("a leader can withdraw the vote", () => {
    render(<ClusterPolitics data={data()} loading={{}} updateData={(keys, funcs) => funcs.forEach((f) => f())} />);
    fireEvent.change(screen.getByLabelText("Your galaxy votes for"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Withdraw vote" }));
    expect(authFetch).toHaveBeenCalledWith("api/cluster/vote", expect.objectContaining({ body: JSON.stringify({ benefit: null }) }));
});

test("anyone else is told who votes", () => {
    render(<ClusterPolitics data={data({ kingdomid: { kd_id: "8" } })} loading={{}} updateData={jest.fn()} />);
    expect(screen.queryByLabelText("Your galaxy votes for")).toBeNull();
    expect(screen.getByText(/Only your galaxy leader casts your galaxy's vote/)).toBeTruthy();
});

test("the galaxies tab lists the cluster's galaxies with their empires and votes", () => {
    render(<ClusterPolitics data={data()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Galaxies (2)" }));
    const mine = screen.getByText("1:1 (yours)").closest("tr");
    expect(within(mine).getByText("The Empire")).toBeTruthy();
    const other = screen.getByText("1:2").closest("tr");
    expect(within(other).getByText("None")).toBeTruthy();
    expect(within(other).getByText("No vote")).toBeTruthy();
});

test("a kingdom in no galaxy sees why", () => {
    render(<ClusterPolitics data={data({ cluster: { message: "You are not in a galaxy" } })} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("You are not in a galaxy")).toBeTruthy();
});
