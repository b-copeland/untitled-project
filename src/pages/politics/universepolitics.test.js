import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import UniversePolitics from "./universepolitics";
import { authFetch } from "../../auth";

jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ message: "ok" }) }));
});

const inMs = (ms) => new Date(Date.now() + ms).toISOString();
const option = (key, name, desc, my_votes = 0) => ({ key, name, desc, my_votes });

const universe = (overrides = {}) => ({
    election: { open: true, start: inMs(-3600000), end: inMs(2 * 3600000 + 30000) },
    ballot: [
        { key: "primitives", name: "Primitives", first_election_only: true,
          options: [option("native_reserves", "Native Reserves", "Robbing primitives yields 30% less money", 4),
                    option("wilderness_protection", "Wilderness Protection", "Primitives defend 30% harder")] },
    ],
    active: [{ key: "land_tax", policy_name: "Rules of War", name: "Land Tax", desc: "Settling costs 15% more", hits_me: true },
             { key: "progressive_tax", policy_name: "Wealth", name: "Progressive Tax", desc: "The 10 kingdoms with the most networth earn 10% less money", hits_me: false }],
    votes_cost: 10000,
    ...overrides,
});

const show = (data, updateData = jest.fn()) => render(<UniversePolitics
    data={{ universepolitics: data, kingdom: { votes: 7, money: 100000 }, state: { game_config: {} } }}
    loading={{}} updateData={updateData} />);

test("an open election shows the ballot, my votes, what is in force and when it closes", () => {
    show(universe());
    expect(screen.getByText(/Voting is open, and closes in 2 h 1 min/)).toBeTruthy();
    expect(screen.getByText("On the ballot")).toBeTruthy();
    expect(screen.getByText("(first election only)")).toBeTruthy();
    expect(screen.getByText("Your votes: 4")).toBeTruthy();
    expect(screen.getByText("Rules of War: Land Tax")).toBeTruthy();
    expect(screen.getByText("(not your kingdom)")).toBeTruthy();  // only the leaders pay Progressive Tax
    expect(document.body.textContent).not.toMatch(/epoch/i);
});

test("casting sends the policy, the option and the votes", () => {
    const updateData = jest.fn();
    show(universe(), updateData);
    const buttons = screen.getAllByRole("button", { name: "Cast votes" });
    expect(buttons[0].disabled).toBe(true);  // nothing entered
    fireEvent.change(document.getElementById("votes-native_reserves"), { target: { name: "native_reserves", value: "3" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Cast votes" })[0]);
    expect(updateData).toHaveBeenCalledWith(["universepolitics", "kingdom"], [expect.any(Function)]);
    updateData.mock.calls[0][1][0]();
    expect(authFetch).toHaveBeenLastCalledWith("api/universepolitics/policies", expect.objectContaining({
        body: JSON.stringify({ policy: "primitives", option: "native_reserves", votes: 3 }),
    }));
});

test("between elections it shows the next ballot and no way to cast", () => {
    show(universe({ election: { open: false, start: inMs(26 * 3600000), end: "" }, active: [] }));
    expect(screen.getByText(/The next election opens in 26 h/)).toBeTruthy();
    expect(screen.getByText("On the next ballot")).toBeTruthy();
    expect(screen.getByText("Nothing yet: the first election decides.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Cast votes" })).toBeNull();
});
