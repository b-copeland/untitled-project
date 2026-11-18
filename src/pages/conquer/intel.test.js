import React from "react";
import { render as renderBare, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import IntelMarket, { KingdomIntel, TargetIntel, tradable } from "./intel";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
jest.mock("../kingdominfo.js", () => (props) => <div>Kingdom view of {props.data.kdId}: {props.data.kingdom.name}</div>);

// The pages link to the Spy page, so they are shown inside a router; /spy shows where the link went.
function SpyProbe() {
    return <div>Spy page with {JSON.stringify(useLocation().state)}</div>;
}
const render = (ui) => renderBare(
    <MemoryRouter initialEntries={["/intel"]}>
        <Routes><Route path="/intel" element={ui} /><Route path="/spy" element={<SpyProbe />} /></Routes>
    </MemoryRouter>,
);

const inHours = (hours) => new Date(Date.now() + hours * 3.6e6).toISOString();

const intel = {
    listings: [
        { id: "2.5.military", seller: "2", target: "5", category: "military", cut: 0.1, time: inHours(5), problem: null },
        { id: "3.5.kingdom", seller: "3", target: "5", category: "kingdom", cut: 0.05, time: inHours(5),
          problem: "You already have kingdom intel on this kingdom at a 10.0% cut, and can not take it at a lower one" },
        { id: "1.6.shields", seller: "1", target: "6", category: "shields", cut: 0.1, time: inHours(5), problem: "This is your listing" },
    ],
    bounties: [
        { id: "2.6.drones", requester: "2", target: "6", category: "drones", cut: 0.1, time: inHours(3), problem: "You do not have drones intel on this kingdom", have: false },
        { id: "1.5.shields", requester: "1", target: "5", category: "shields", cut: 0.1, time: inHours(3), problem: "This is your bounty", have: false },
        { id: "3.6.military", requester: "3", target: "6", category: "military", cut: 0.05, time: inHours(4), problem: null, have: true },
    ],
    accepted: [{ target: "5", category: "kingdom", sharer: "3", cut: 0.1, time: inHours(2), source: "market" }],
    cuts: { 5: 0.1 },
    my_intel: [
        { target: "5", category: "kingdom", time: inHours(2), received: true, listing: null, cut: null },
        { target: "6", category: "shields", time: inHours(5), received: false, listing: "1.6.shields", cut: 0.1 },
        { target: "6", category: "military", time: inHours(5), received: false, listing: null, cut: null },
    ],
    exclusions: ["3"],
    history: [{ kind: "purchase", time: inHours(-1), from: "2", to: "3", target: "5", category: "military", cut: 0.1 }],
};

const data = {
    intel,
    kingdomid: { kd_id: "1" },
    kingdom: { kdId: "1" },
    kingdoms: { 1: "Me", 2: "Two", 3: "Three", 5: "Five", 6: "Six" },
    galaxies: { "1:1": ["1", "2", "3"], "2:1": ["5", "6"] },
    galaxies_inverted: { 1: "1:1", 2: "1:1", 3: "1:1", 5: "2:1", 6: "2:1" },
    notifs: { shared: 0 },
    state: {
        reveal_operations: ["spykingdom", "spymilitary", "spyshields", "spyprojects", "spystructures", "spydrones"],
        game_config: { BASE_MAX_SHARE_CUT: 0.15, BASE_MAX_TOTAL_SHARE_CUT: 0.3, BASE_INTEL_BOUNTY_MAX_EPOCHS: 48 },
    },
};

let updateData;
const sentBodies = () => updateData.mock.calls.map(([, [send]]) => { send(); return authFetch.mock.calls[authFetch.mock.calls.length - 1]; });

beforeEach(() => {
    updateData = jest.fn();
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ message: "ok" }) }));
});

// Every tab's pane is in the page; look only in the one showing.
const pane = () => within(document.querySelector(".tab-pane.active") || document.body);
const row = (text) => pane().getAllByText(text)[0].closest("tr");

test("the market tab buys a listing, and a listing that can not be taken says why", () => {
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: /Market/ }));
    const military = row("military");
    fireEvent.click(within(military).getByRole("button", { name: "Buy" }));
    const [[route, request]] = sentBodies();
    expect(route).toBe("api/intel/buy");
    expect(JSON.parse(request.body)).toEqual({ listing: "2.5.military" });
    expect(updateData.mock.calls[0][0]).toEqual(["intel", "revealed"]);

    const blocked = pane().getAllByRole("button", { name: "Buy" }).find((button) => button.disabled);
    expect(blocked.getAttribute("title")).toMatch(/lower one/);
    expect(pane().getByRole("button", { name: "Remove" })).toBeTruthy();  // my own listing
    expect(pane().getByText("Three bought from Two")).toBeTruthy();
});

test("the bounties tab fulfils, withdraws, and asks for intel", () => {
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    // Only the bounty for intel you have offers Fulfil.
    const fulfil = within(row("military")).getByRole("button", { name: "Fulfil" });
    expect(pane().getAllByRole("button", { name: "Fulfil" })).toHaveLength(1);
    fireEvent.click(fulfil);
    fireEvent.click(pane().getByRole("button", { name: "Withdraw" }));
    const post = pane().getByRole("button", { name: "Post bounty" });
    expect(post.disabled).toBe(true);
    expect(post.getAttribute("title")).toBe("Choose a kingdom");
    const sent = sentBodies();
    expect(sent.map(([route]) => route)).toEqual(["api/intel/fulfil", "api/intel/cancelbounty"]);
    expect(JSON.parse(sent[0][1].body)).toEqual({ bounty: "3.6.military" });
    expect(JSON.parse(sent[1][1].body)).toEqual({ bounty: "1.5.shields" });
});

test("a bounty for intel you do not have offers to spy for it", () => {
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    const drones = row("drones");
    expect(within(drones).queryByRole("button", { name: "Fulfil" })).toBeNull();
    fireEvent.click(within(drones).getByRole("button", { name: "Attempt" }));
    expect(screen.getByText('Spy page with {"kdId":"6","operation":"spydrones"}')).toBeTruthy();
});

test("a page that is itself the spy page takes the operation in place", () => {
    const onAttempt = jest.fn();
    render(<KingdomIntel data={data} loading={{}} updateData={updateData} target="6" onAttempt={onAttempt} />);
    fireEvent.click(screen.getByRole("button", { name: "Attempt" }));
    expect(onAttempt).toHaveBeenCalledWith("6", "spydrones");
});

test("a bounty left without a length is posted without one, for the server's longest", () => {
    render(<KingdomIntel data={data} loading={{}} updateData={updateData} target="6" />);
    expect(screen.getByLabelText(/Stays up for/).getAttribute("placeholder")).toBe("48");
    fireEvent.keyDown(document.getElementById("bounty-category"), { key: "ArrowDown" });  // opens the picker
    fireEvent.click(screen.getAllByText("drones").pop());  // its menu is the last thing on the page
    const post = screen.getByRole("button", { name: "Post bounty" });
    expect(post.disabled).toBe(false);
    fireEvent.click(post);
    const [[route, request]] = sentBodies();
    expect(route).toBe("api/intel/bounty");
    expect(JSON.parse(request.body)).toEqual({ target: "6", category: "drones", cut: 0 });
});

test("every row you can act on can show its kingdom", async () => {
    authFetch.mockImplementation((url) => Promise.resolve({ json: () => Promise.resolve(url === "api/kingdom/5" ? { name: "Five's details" } : {}) }));
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: /Market/ }));
    fireEvent.click(within(row("military")).getByRole("button", { name: "View kingdom" }));
    expect(await screen.findByText("Kingdom view of 5: Five's details")).toBeTruthy();
    for (const tab of [/Bounties/, "Your intel"]) {
        fireEvent.click(screen.getByRole("tab", { name: tab }));
        expect(pane().getAllByRole("button", { name: "View kingdom" }).length).toBeGreaterThan(0);
    }
});

test("listings of intel you have already taken are shaded and tagged", () => {
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: /Market/ }));
    const listings = pane().getAllByRole("table")[0];
    const kingdom = within(listings).getByText("kingdom").closest("tr");
    expect(kingdom.className).toBe("intel-row-taken");
    expect(within(kingdom).getByText("taken")).toBeTruthy();
    expect(within(listings).getByText("military").closest("tr").className).toBe("");
});

test("a cut over the most is refused before sending", () => {
    render(<KingdomIntel data={data} loading={{}} updateData={updateData} target="6" />);
    fireEvent.change(screen.getByLabelText("Cut", { selector: "#bounty-cut" }), { target: { value: "20" } });
    expect(screen.getByText("At most 15%")).toBeTruthy();
});

test("your intel lists for a cut or shares free, and received intel can not be passed on", () => {
    render(<IntelMarket data={data} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("tab", { name: "Your intel" }));
    expect(within(row("kingdom")).getByText("can not be passed on")).toBeTruthy();
    const military = row("military");
    const list = within(military).getByRole("button", { name: "List" });
    expect(list.disabled).toBe(true);
    fireEvent.change(within(military).getByLabelText("Cut"), { target: { value: "12" } });
    fireEvent.click(within(military).getByRole("button", { name: "List" }));
    fireEvent.click(within(military).getByRole("button", { name: "Share free" }));
    const sent = sentBodies();
    expect(sent.map(([route]) => route)).toEqual(["api/intel/share", "api/intel/share"]);
    expect(JSON.parse(sent[0][1].body)).toEqual({ target: "6", category: "military", cut: "12" });
    expect(JSON.parse(sent[1][1].body)).toEqual({ target: "6", category: "military", cut: 0 });
    // Exclusions: Three is kept out; letting Three back in and saving sends the new list.
    const three = pane().getByLabelText("Three");
    expect(three.checked).toBe(true);
    fireEvent.click(three);
    fireEvent.click(pane().getByRole("button", { name: "Save" }));
    const last = authFetch.mock.calls.length;
    updateData.mock.calls[updateData.mock.calls.length - 1][1][0]();
    expect(JSON.parse(authFetch.mock.calls[last][1].body)).toEqual({ excluded: [] });
});

test("one kingdom's intel shows only that kingdom", async () => {
    render(<KingdomIntel data={data} loading={{}} updateData={updateData} target="6" />);
    expect(screen.getByText("Intel on Six")).toBeTruthy();
    expect(screen.queryByText("can not be passed on")).toBeNull();  // that intel is on Five
    expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(2);  // my shields listing on Six, in both tables
    expect(screen.queryAllByRole("button", { name: "Buy" })).toHaveLength(0);  // the listings for sale are on Five
    expect(screen.getByText("drones")).toBeTruthy();  // Two's bounty on Six
    fireEvent.click(screen.getByRole("button", { name: "View kingdom" }));  // one button: every row is on Six
    expect(await screen.findByText(/Kingdom view of 6/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hide kingdom" })).toBeTruthy();
    expect(screen.queryByLabelText("Kingdom", { selector: "input" })).toBeNull();  // the bounty form is for Six
});

test("intel is traded only on kingdoms outside your galaxy", () => {
    expect(tradable(data, "5")).toBe(true);
    expect(tradable(data, "2")).toBe(false);  // a galaxymate
    expect(tradable(data, "1")).toBe(false);  // yourself
    expect(tradable(data, undefined)).toBe(false);
});

test("a planner page's target line says what you give up and opens the market in place", () => {
    const { container } = render(<TargetIntel data={data} loading={{}} updateData={updateData} target="5" />);
    expect(container.textContent).toMatch(/kingdom from Three \(10\.0%\)/);
    expect(container.textContent).toMatch(/get 10\.0% of what you win/);
    expect(container.textContent).toMatch(/1 for sale, 1 bounty/);  // the kingdom listing can not be taken
    fireEvent.click(screen.getByRole("button", { name: "Intel market" }));
    expect(screen.getByText("Intel on Five")).toBeTruthy();
});

test("there is no target line for a galaxymate or before a target is chosen", () => {
    const { container: mate } = render(<TargetIntel data={data} loading={{}} updateData={updateData} target="2" />);
    expect(mate.textContent).toBe("");
    const { container: none } = render(<TargetIntel data={data} loading={{}} updateData={updateData} target={undefined} />);
    expect(none.textContent).toBe("");
});
