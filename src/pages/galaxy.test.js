import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Galaxy from "./galaxy";
import { authFetch } from "../auth";

jest.mock("../components/header", () => () => null);
jest.mock("../components/helpbutton", () => () => null);
jest.mock("./kingdominfo.js", () => () => null);
jest.mock("./conquer/attack.js", () => () => null);
jest.mock("./conquer/spy.js", () => () => null);
jest.mock("./conquer/launchmissiles.js", () => () => null);
jest.mock("./message.js", () => () => null);
jest.mock("../auth", () => ({ authFetch: jest.fn() }));

const galaxyInfo = {
    2: { name: "Delta", race: "Xo", stars: 400, networth: 12345, coordinate: 40, status: "Active",
         military_estimate: { offense: 9000, defense: 5000 } },
    3: { name: "Echo", race: "Gaian", coordinate: 10, status: "Active" },
};
const data = {
    galaxies: { "1:1": [] }, galaxies_inverted: { 1: "1:1", 2: "1:1", 3: "1:1" }, kingdoms: { 1: "Me", 2: "Delta", 3: "Echo" },
    kingdom: { kdId: "1", coordinate: 0 }, pinned: [], revealed: { revealed: { 2: { military: new Date(Date.now() + 3 * 3.6e6 + 60000).toISOString() } } },
    shields: {},
};
const show = () => render(<MemoryRouter><Galaxy data={data} loading={{}} updateData={jest.fn()} initialGalaxyId="1:1" /></MemoryRouter>);
const narrow = (matches) => { window.matchMedia = (query) => ({ matches, media: query, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }); };

beforeEach(() => {
    window.localStorage.clear();
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(galaxyInfo) }));
});

test("a phone-sized screen starts on cards, with the army ceiling and how fresh the intel is", async () => {
    narrow(true);
    show();
    await waitFor(() => expect(screen.getByText("Delta")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Cards" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("≤ 9,000")).toBeTruthy();
    expect(screen.getByText("≤ 5,000")).toBeTruthy();
    expect(screen.getByText("12,345")).toBeTruthy();
    expect(screen.getByText("military 3h")).toBeTruthy();
    // Echo has nothing revealed: unknowns say so rather than showing zero.
    expect(screen.getAllByText("?").length).toBeGreaterThan(3);
});

test("a wide screen starts on the table, and the choice is remembered", async () => {
    narrow(false);
    const { unmount } = show();
    await waitFor(() => expect(screen.getByText("Delta")).toBeTruthy());
    expect(screen.getByRole("table")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cards" }));
    unmount();
    show();
    await waitFor(() => expect(screen.getByText("Delta")).toBeTruthy());
    expect(screen.queryByRole("table")).toBeNull();
});
