import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Schedule from "./schedule";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../../auth");

beforeEach(() => authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "Done" }) })));

const data = {
    kingdom: { schedule: [] }, kingdomid: { kd_id: "1" }, kingdoms: { 1: "Mine", 2: "Theirs" },
    galaxies_inverted: { 1: "1:1", 2: "1:2" }, state: { pretty_names: {} }, missiles: {},
};

const renderPage = () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<MemoryRouter><Schedule data={data} loading={{}} updateData={updateData} /></MemoryRouter>);
};

const choose = (title) => fireEvent.click(screen.getByRole("radio", { name: new RegExp(`^${title}`) }));
const radio = (label) => screen.getByLabelText(new RegExp(`^${label}`), { selector: "input" });
const type = (label, value) => fireEvent.change(screen.getAllByLabelText(label).find((el) => el.tagName === "INPUT"), { target: { value } });

test("an attack sends a share of the army by default and primitives send up to a share", () => {
    renderPage();
    choose("Attack Attack a kingdom");
    expect(radio("Send X% of total units").checked).toBe(true);
    expect(radio("Send up to X% of total units, including units already out on generals").checked).toBe(false);
    expect(screen.getByLabelText(/^Without military intel, send the share anyway/).checked).toBe(true);

    choose("Attack primitives");
    expect(radio("Send up to X% of total units, including units already out on generals").checked).toBe(true);
});

test("a schedule with no attackers and no flexers says why it can not be sent", () => {
    renderPage();
    choose("Attack primitives");
    expect(screen.getByText("Send some attackers or flexers")).toBeTruthy();
    type("Flexers to send", "25");  // no attackers, some flexers: fine
    expect(screen.queryByText("Send some attackers or flexers")).toBeNull();
});

test("the chosen way of counting goes to the server", () => {
    renderPage();
    choose("Attack primitives");
    fireEvent.click(radio("Send X% of total units"));
    type("Attackers to send", "25");
    fireEvent.click(screen.getByRole("button", { name: "Schedule it" }));
    const body = JSON.parse(authFetch.mock.calls[0][1].body);
    expect(body.type).toBe("attackprimitives");
    expect(body.options).toMatchObject({ units_mode: "send", pure_offense: "25", flex_offense: "" });
});

test("?tab=repeating opens the Repeating tab (the Spy page links there)", () => {
    render(<MemoryRouter initialEntries={["/schedule?tab=repeating"]}><Schedule data={data} loading={{}} updateData={jest.fn()} /></MemoryRouter>);
    expect(screen.getByRole("tab", { name: /Repeating/ }).getAttribute("aria-selected")).toBe("true");
});
