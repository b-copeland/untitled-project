import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { createQueryClient } from "./data/gameData";
import { useAuth, authFetch } from "./auth";

// Where a player is sent depends on whether they have a kingdom: the pages themselves don't matter here.
jest.mock("./auth", () => ({
    useAuth: jest.fn(), authFetch: jest.fn(), login: jest.fn(), logout: jest.fn(), getSession: jest.fn(), getSessionState: jest.fn(),
}));
jest.mock("./pages/createkingdom.js", () => ({ __esModule: true, default: () => <div>creator page</div> }));
jest.mock("./pages/home/status.js", () => ({ __esModule: true, default: () => <div>status page</div> }));
jest.mock("./pages/login.js", () => ({ __esModule: true, default: () => <div>login page</div> }));

let kingdomid;

beforeEach(() => {
    global.WebSocket = class { constructor() { setTimeout(() => this.onerror && this.onerror(), 0); } close() {} send() {} };
    authFetch.mockReset();
    authFetch.mockImplementation((url) => Promise.resolve({ json: () => Promise.resolve(url === "api/kingdomid" ? kingdomid : {}) }));
    useAuth.mockReturnValue([true, { accessToken: "token" }]);
});

const renderAt = (path) => render(
    <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    </QueryClientProvider>
);

test("a player with no kingdom is sent to make one, and the menu offers nothing else", async () => {
    kingdomid = { kd_id: "", created: false };
    renderAt("/status");

    expect(await screen.findByText("creator page")).toBeTruthy();
    expect(screen.getAllByText("Create your kingdom").length).toBeGreaterThan(0);
    expect(screen.queryByText("Structures")).toBeNull();
});

test("so is a player whose kingdom was made but never set up", async () => {
    kingdomid = { kd_id: "7", created: false };
    renderAt("/attack");
    expect(await screen.findByText("creator page")).toBeTruthy();
});

test("a player with a kingdom goes to the game, with the whole menu, and can not reopen the creator", async () => {
    kingdomid = { kd_id: "7", created: true };
    renderAt("/createkingdom");

    expect(await screen.findByText("status page")).toBeTruthy();
    expect(screen.queryByText("creator page")).toBeNull();
    expect(screen.getAllByText("Structures").length).toBeGreaterThan(0);
    expect(screen.queryByText("Create your kingdom")).toBeNull();
});

test("someone signed out can not open the creator", async () => {
    useAuth.mockReturnValue([false, null]);
    kingdomid = {};
    renderAt("/createkingdom");

    expect(await screen.findByText("login page")).toBeTruthy();
    expect(screen.queryByText("creator page")).toBeNull();
});
