import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import GalaxyPolitics from "./galaxypolitics";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ message: "ok" }) }));
});

const inMs = (ms) => new Date(Date.now() + ms).toISOString();

const politics = (overrides = {}) => ({
    votes: { leader: { 1: "1" }, policy_1: { 1: "1" }, policy_2: {} },
    leader: "1", policy_1_winner: "1", policy_2_winner: "",
    desc: {
        policy_1: { name: "Doctrine A", options: { 1: { name: "A1", desc: "first" }, 2: { name: "A2", desc: "second" } } },
        policy_2: { name: "Doctrine B", options: { 1: { name: "B1", desc: "first" }, 2: { name: "B2", desc: "second" } } },
    },
    vote_cooldown_hours: 3,
    vote_unlocks_at: { leader: null, policy_1: null, policy_2: null },
    ...overrides,
});

const data = (galaxypolitics) => ({
    galaxypolitics,
    kingdomid: { kd_id: "1" },
    kingdom: { kdId: "1" },
    kingdoms: { 1: "Me", 2: "Two" },
    galaxies: { "1:1": ["1", "2"] },
    galaxies_inverted: { 1: "1:1", 2: "1:1" },
});

// Every tab's pane is in the page; look only in the one showing.
const pane = () => within(document.querySelector(".tab-pane.active"));

const show = (galaxypolitics, updateData = jest.fn()) =>
    render(<GalaxyPolitics data={data(galaxypolitics)} loading={{}} updateData={updateData} />);

test("a vote that can change says how long a change holds", () => {
    show(politics());
    expect(pane().getByText("Once you change a vote, it stays for 3 hours.")).toBeTruthy();
    expect(pane().queryByText(/changed this vote recently/)).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Policies" }));
    expect(pane().getAllByText("Once you change a vote, it stays for 3 hours.")).toHaveLength(1);
});

test("a locked leader vote says when it can change, and can not be sent", () => {
    const updateData = jest.fn();
    show(politics({ vote_unlocks_at: { leader: inMs(2 * 3600000 + 4 * 60000 + 30000), policy_1: null, policy_2: null } }), updateData);
    expect(pane().getByText("You changed this vote recently. You can change it again in 2 h 5 min.")).toBeTruthy();
    const vote = pane().getByRole("button", { name: "Vote" });
    expect(vote.disabled).toBe(true);
    fireEvent.click(vote);
    expect(updateData).not.toHaveBeenCalled();
});

test("a locked policy vote locks only that doctrine's buttons", () => {
    show(politics({ vote_unlocks_at: { leader: null, policy_1: inMs(3600000), policy_2: null } }));
    fireEvent.click(screen.getByRole("tab", { name: "Policies" }));
    expect(pane().getAllByText(/You can change it again in 1 h/)).toHaveLength(1);  // only doctrine A says so
    const votes = pane().getAllByRole("button", { name: /Vote|Already Voting/ });
    // Doctrine A: already voting for 1, locked for 2. Doctrine B: both open.
    expect(votes.map((button) => button.disabled)).toEqual([true, true, false, false]);
    expect(votes[1].getAttribute("title")).toMatch(/changed this vote recently/);
    expect(document.body.textContent).not.toMatch(/epoch/i);
});
