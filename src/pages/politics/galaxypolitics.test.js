import React from "react";
import { render as renderBare, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import GalaxyPolitics from "./galaxypolitics";
import { authFetch } from "../../auth";

// Kingdom names link to their pages, so the page is shown inside a router.
const render = (element) => renderBare(<MemoryRouter>{element}</MemoryRouter>);

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ message: "ok" }) }));
});

const inMs = (ms) => new Date(Date.now() + ms).toISOString();

const option = (key, name, desc, votes = 0, weight = 0) => ({ key, name, desc, votes, weight, effects: {} });

const politics = (overrides = {}) => ({
    votes: { leader: { 1: "1" } },
    leader: "1",
    policies: [
        {
            key: "growth_doctrine", name: "Growth Doctrine", active: "expansionist", my_vote: "expansionist",
            options: [option("expansionist", "Expansionist", "Settling costs 15% less", 1, 0.75),
                      option("raiders", "Raiders", "Attacks on primitives gain 20% more stars", 1, 0.25)],
        },
        {
            key: "arsenal", name: "Arsenal", active: null, my_vote: null,
            options: [option("silo_programme", "Silo Programme", "Missiles cost 20% less"),
                      option("aegis", "Aegis", "Missile shields cost 50% less fuel")],
        },
    ],
    next_tally: inMs(90 * 60000 + 30000),
    tally_hours: 6,
    vote_cooldown_hours: 3,
    vote_unlocks_at: { leader: null },
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

const policiesTab = () => fireEvent.click(screen.getByRole("tab", { name: "Policies" }));

test("the leader vote says how long a change holds", () => {
    show(politics());
    expect(pane().getByText("Once you change a vote, it stays for 3 hours.")).toBeTruthy();
    expect(pane().queryByText(/changed this vote recently/)).toBeNull();
});

test("a locked leader vote says when it can change, and can not be sent", () => {
    const updateData = jest.fn();
    show(politics({ vote_unlocks_at: { leader: inMs(2 * 3600000 + 4 * 60000 + 30000) } }), updateData);
    expect(pane().getByText("You changed this vote recently. You can change it again in 2 h 5 min.")).toBeTruthy();
    const vote = pane().getByRole("button", { name: "Vote" });
    expect(vote.disabled).toBe(true);
    fireEvent.click(vote);
    expect(updateData).not.toHaveBeenCalled();
});

test("the policies tab shows the round's policies, what is active, and the next tally", () => {
    show(politics());
    policiesTab();
    expect(pane().getByText("Growth Doctrine")).toBeTruthy();
    expect(pane().getByText("Arsenal")).toBeTruthy();
    expect(pane().getByText("(active)")).toBeTruthy();  // only Expansionist is active
    expect(pane().getByText("Missile shields cost 50% less fuel")).toBeTruthy();
    expect(pane().getByText(/every 6 hours; the next is in 1 h 31 min/)).toBeTruthy();
    expect(pane().getByText(/Votes: 1\. Share of the time held towards the next tally: 75\.0%/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/epoch/i);
    // Policy votes never lock: no wait, nothing disabled.
    expect(pane().queryByText(/changed this vote recently/)).toBeNull();
    expect(pane().getAllByRole("button").every((button) => !button.disabled)).toBe(true);
});

test("voting sends the policy and option, and its own vote can be withdrawn", () => {
    const updateData = jest.fn();
    show(politics(), updateData);
    policiesTab();
    const growth = within(pane().getByText("Growth Doctrine").closest(".galaxy-policy"));
    expect(growth.getAllByRole("button").map((button) => button.textContent)).toEqual(["Withdraw my vote", "Vote"]);
    fireEvent.click(growth.getByRole("button", { name: "Vote" }));
    expect(updateData).toHaveBeenLastCalledWith(["galaxypolitics"], [expect.any(Function)]);
    updateData.mock.calls[0][1][0]();
    expect(authFetch).toHaveBeenLastCalledWith("api/galaxypolitics/policies", expect.objectContaining({
        method: "POST", body: JSON.stringify({ policy: "growth_doctrine", option: "raiders" }),
    }));
    fireEvent.click(growth.getByRole("button", { name: "Withdraw my vote" }));
    updateData.mock.calls[1][1][0]();
    expect(authFetch).toHaveBeenLastCalledWith("api/galaxypolitics/policies", expect.objectContaining({
        body: JSON.stringify({ policy: "growth_doctrine", option: "" }),
    }));
});

test("a page with no policies yet shows none and does not break", () => {
    show(politics({ policies: undefined, next_tally: undefined, tally_hours: undefined }));
    policiesTab();
    expect(pane().getByText("Galaxy Policies")).toBeTruthy();
    expect(pane().queryByRole("button")).toBeNull();
});
