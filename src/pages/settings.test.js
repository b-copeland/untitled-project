import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Settings from "./settings";

jest.mock("../components/helpbutton", () => () => null);
jest.mock("../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../auth");

const options = [{ value: "gray", label: "Gray" }, { value: "light", label: "Light" }, { value: "nebula", label: "Nebula" }];
const updateData = jest.fn();
const answer = (body) => authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve(body) }));

beforeEach(() => {
    updateData.mockImplementation((keys, funcs) => funcs.forEach((f) => f()));
    answer({ status: "success", message: "Settings saved" });
    document.documentElement.removeAttribute("data-theme");
});

const renderPage = (theme = "gray") => render(<Settings data={{ preferences: { theme, options: { theme: options } } }} loading={{}} updateData={updateData} />);

test("every theme is offered with a preview in its own colours, and the saved one is chosen", () => {
    renderPage("light");
    expect(screen.getAllByRole("radio").map((radio) => radio.getAttribute("aria-label"))).toEqual(["Gray", "Light", "Nebula"]);
    expect(screen.getByRole("radio", { name: /Light/ }).getAttribute("aria-checked")).toBe("true");
    expect(document.querySelector('.theme-preview[data-theme="nebula"]')).toBeTruthy();
});

test("choosing a theme shows it at once and saves it to the account", () => {
    renderPage();
    fireEvent.click(screen.getByRole("radio", { name: /Nebula/ }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("nebula");
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("dark");
    expect(authFetch).toHaveBeenCalledWith("api/preferences", expect.objectContaining({ body: JSON.stringify({ theme: "nebula" }) }));
    expect(updateData).toHaveBeenCalledWith(["preferences"], [expect.any(Function)]);
});

test("the light theme turns Bootstrap's light mode on", () => {
    renderPage();
    fireEvent.click(screen.getByRole("radio", { name: /Light/ }));
    expect(document.documentElement.getAttribute("data-bs-theme")).toBe("light");
});

test("if the save fails, the theme goes back", async () => {
    answer({ message: "Your settings could not be saved. Try again." });
    renderPage();
    fireEvent.click(screen.getByRole("radio", { name: /Nebula/ }));
    await screen.findByText("Your settings could not be saved. Try again.");
    expect(document.documentElement.getAttribute("data-theme")).toBe("gray");
});

const muteOptions = [
    { value: "settles", label: "Settles", group: "Your kingdom" },
    { value: "generals", label: "Generals", group: "Your kingdom" },
    { value: "attacked", label: "Attacks on you", group: "Against you" },
];
const renderWithMuted = (muted) => render(<Settings data={{ preferences: { theme: "gray", muted, options: { theme: options, muted: muteOptions } } }}
    loading={{}} updateData={updateData} />);

test("each kind of notification has a switch, in its group, on unless the player turned it off", () => {
    renderWithMuted(["generals"]);
    expect(screen.getByRole("group", { name: "Your kingdom" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Against you" })).toBeTruthy();
    expect(screen.getByRole("switch", { name: "Settles" }).checked).toBe(true);
    expect(screen.getByRole("switch", { name: "Generals" }).checked).toBe(false);
});

test("turning a notification off saves the whole list, and a refusal turns it back on", async () => {
    renderWithMuted(["generals"]);
    fireEvent.click(screen.getByRole("switch", { name: "Settles" }));
    expect(authFetch).toHaveBeenCalledWith("api/preferences", expect.objectContaining({ body: JSON.stringify({ muted: ["generals", "settles"] }) }));
    expect(screen.getByRole("switch", { name: "Settles" }).checked).toBe(false);

    answer({ status: "error", message: "Your settings could not be saved. Try again." });
    fireEvent.click(screen.getByRole("switch", { name: "Attacks on you" }));
    expect(await screen.findByText("Your settings could not be saved. Try again.")).toBeTruthy();
    expect(screen.getByRole("switch", { name: "Attacks on you" }).checked).toBe(true);
});

test("the advisors can be switched off, and are on until the player says so", () => {
    renderPage();
    const toggle = screen.getByRole("switch", { name: "Show advice on the Status page" });
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    expect(authFetch).toHaveBeenCalledWith("api/preferences", expect.objectContaining({ body: JSON.stringify({ advisors: "off" }) }));
    expect(toggle.checked).toBe(false);
});
