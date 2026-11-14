import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Automation, { automations, spendingSummary } from "./automation";

jest.mock("../components/header", () => () => null);
jest.mock("../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../auth");

beforeEach(() => authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "Done" }) })));

const sw = (name) => screen.getAllByLabelText(name).find((element) => element.tagName === "INPUT");

const kingdom = {
    auto_spending_enabled: true, auto_spending: { settle: 0.1, structures: 0.2, military: 0.6, engineers: 0 },
    auto_assign_projects: false,
    auto_attack_enabled: false, auto_attack_settings: { pure: 0, flex: 0 },
    auto_rob_enabled: false, auto_rob_settings: { drones: 0.5, shielded: true, keep: 5 },
    schedule: [{}, {}],
};

const renderPage = () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<MemoryRouter><Automation data={{ kingdom }} loading={{}} updateData={updateData} /></MemoryRouter>);
    return updateData;
};

test("the spending split reads biggest first and leaves out what gets nothing", () => {
    expect(spendingSummary(kingdom.auto_spending)).toBe("60.0% military, 20.0% structures, 10.0% settling");
    expect(spendingSummary({})).toMatch(/No share set/);
});

test("every automatic feature is on the page with whether it is on and what it will do", () => {
    renderPage();
    ["Auto spending", "Engineers on projects", "Attack primitives", "Rob primitives", "Scheduled actions"]
        .forEach((title) => expect(screen.getByRole("region", { name: title })).toBeTruthy());
    expect(sw("Auto spending").checked).toBe(true);
    expect(sw("Engineers on projects").checked).toBe(false);
    expect(screen.getByText(/Sends 50.0% of drones shielded, keeps 5 spy attempts/)).toBeTruthy();
    expect(screen.getByText("2 waiting")).toBeTruthy();
    expect(screen.getByText(/1 of 4 automatic features are on/)).toBeTruthy();
});

test("a switch calls the route that feature already has, with the new setting", () => {
    renderPage();
    fireEvent.click(sw("Engineers on projects"));
    expect(authFetch).toHaveBeenCalledWith("api/projects/target", expect.objectContaining({ body: JSON.stringify({ enabled: true }) }));
    fireEvent.click(sw("Auto spending"));
    expect(authFetch).toHaveBeenCalledWith("api/spending", expect.objectContaining({ body: JSON.stringify({ enabled: false }) }));
});

test("auto attack can not be switched on until it has a share of units to send, and says why", () => {
    renderPage();
    expect(sw("Attack primitives").disabled).toBe(true);
    expect(screen.getByText(/Set the share of units to send before turning this on/)).toBeTruthy();
    expect(sw("Rob primitives").disabled).toBe(false);
});

test("each feature links to the page with its settings", () => {
    renderPage();
    expect(screen.getByText("Project targets").getAttribute("href")).toBe("/projects");
    expect(screen.getByText("Rob settings").getAttribute("href")).toBe("/primitives");
    expect(automations({}).every((item) => item.links.length > 0)).toBe(true);
});
