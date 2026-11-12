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

test("help opens on the topic for the page it was asked from", () => {
    render(<MemoryRouter><Help scrollTarget="spy" /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { name: "Conquer - Spy" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Guide" })).toBeNull();
});
