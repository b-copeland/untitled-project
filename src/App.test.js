import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { createQueryClient } from "./data/gameData";

beforeEach(() => {
    localStorage.clear();
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ state: {} }) }));
    global.WebSocket = class { constructor() { setTimeout(() => this.onerror && this.onerror(), 0); } close() {} send() {} };
});

const renderAt = (path) => render(
    <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
    </QueryClientProvider>
);

test("the landing page opens at /", async () => {
    renderAt("/");
    expect(await screen.findByText(/Welcome to/)).toBeTruthy();
});

test("the login form opens at /login", async () => {
    renderAt("/login");
    expect(await screen.findByPlaceholderText("Username")).toBeTruthy();
});

test("a signed-out visitor sent to a game page lands on the login page", async () => {
    renderAt("/attack");
    expect(await screen.findByPlaceholderText("Username")).toBeTruthy();
});

test("the account recovery pages are open to everyone", async () => {
    renderAt("/forgot");
    expect(await screen.findByText("Recover your account")).toBeTruthy();
});
