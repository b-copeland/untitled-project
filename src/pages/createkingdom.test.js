import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreateKingdom from "./createkingdom";
import { authFetch } from "../auth";

jest.mock("../auth", () => ({ authFetch: jest.fn() }));
jest.mock("../components/helpbutton", () => () => null);

const CREATOR = {
    total_points: 100,
    total_stars: 10,
    selection_points: { drones: 1, recruits: 1, attack: 5, defense: 5, flex: 8, engineers: 10 },
    presets: [
        {
            key: "explorer", label: "Explorer", description: "Claims stars.", race: "Gaian",
            unitsChoices: { drones: 50, recruits: 20, attack: 0, defense: 6, flex: 0, engineers: 0 },
            structuresChoices: { homes: 6, mines: 4 },
            autoSpending: { settle: 0.5, structures: 0.3 }, autoAttack: false, autoRob: false,
        },
        {
            key: "attacker", label: "Attacker", description: "Hits others.", race: "Xo",
            unitsChoices: { drones: 50, recruits: 20, attack: 6, defense: 0, flex: 0, engineers: 0 },
            structuresChoices: { homes: 5, mines: 5 },
            autoSpending: { military: 0.6 }, autoAttack: true, autoRob: false,
        },
    ],
};

const STATE = {
    races: ["Gaian", "Xo"],
    game_config: {},
    units: { attack: { offense: 5 }, defense: { defense: 5 } },
    structures: { pop_per_home: 10, income_per_mine: 2 },
    income_per_pop: 1,
};

let posted;

const respond = (value, ok = true) => Promise.resolve({ ok, status: ok ? 200 : 400, json: () => Promise.resolve(value) });

beforeEach(() => {
    posted = [];
    authFetch.mockReset();
    authFetch.mockImplementation((url, options) => {
        if (url === "api/createkingdomdata") return respond(CREATOR);
        posted.push({ url, body: JSON.parse(options.body) });
        return respond({ message: "" });
    });
});

const renderPage = (extra = {}) => {
    const updateData = jest.fn(() => Promise.resolve());
    const props = { kingdomid: { kd_id: "", created: false }, kingdoms: { 1: "Taken Name" }, state: STATE, updateData, ...extra };
    render(<CreateKingdom {...props} />);
    return updateData;
};

const settled = () => waitFor(() => expect(screen.getByRole("button", { name: "Create kingdom" }).disabled).toBe(false));

const next = () => fireEvent.click(screen.getByRole("button", { name: "Next" }));
const typeName = (value) => fireEvent.change(screen.getByLabelText("Kingdom name"), { target: { value } });

test("the name step does not move on until the name is usable", async () => {
    renderPage();
    await screen.findByText("Name your kingdom");
    expect(screen.getByRole("button", { name: "Next" }).disabled).toBe(true);

    typeName("taken name");
    expect(screen.getByText("Another kingdom already has that name")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next" }).disabled).toBe(true);

    typeName("x".repeat(25));
    expect(screen.getByText("Names are at most 24 characters")).toBeTruthy();

    typeName("Fresh Name");
    expect(screen.getByRole("button", { name: "Next" }).disabled).toBe(false);
});

test("a quick start is created in one request, after asking about the auto builder", async () => {
    const updateData = renderPage();
    await screen.findByText("Name your kingdom");
    typeName("  Fresh Name ");
    next();

    expect(screen.getByRole("button", { name: "Next" }).disabled).toBe(true); // nothing chosen yet
    fireEvent.click(screen.getByRole("radio", { name: /Attacker/ }));
    next();
    expect(screen.getByText("Ready?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));

    expect(await screen.findByText("Switch on the auto builder?")).toBeTruthy();
    expect(screen.getByText(/sends units against primitives/)).toBeTruthy();
    expect(posted).toEqual([]); // not yet
    fireEvent.click(screen.getByRole("button", { name: "Keep it off" }));

    await waitFor(() => expect(updateData).toHaveBeenCalledWith(["kingdomid"]));
    expect(posted).toEqual([{ url: "api/createkingdom", body: { preset: "attacker", autoBuilder: false, kdName: "Fresh Name" } }]);
    await settled();
});

test("switching the auto builder on is sent", async () => {
    renderPage();
    await screen.findByText("Name your kingdom");
    typeName("Fresh");
    next();
    fireEvent.click(screen.getByRole("radio", { name: /Explorer/ }));
    next();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));
    fireEvent.click(await screen.findByRole("button", { name: "Switch it on" }));

    await waitFor(() => expect(posted.length).toBe(1));
    expect(posted[0].body).toEqual({ preset: "explorer", autoBuilder: true, kdName: "Fresh" });
    await settled();
});

test("a custom kingdom is blocked until every point and star is spent", async () => {
    renderPage();
    await screen.findByText("Name your kingdom");
    typeName("Mine");
    next();
    fireEvent.click(screen.getByRole("radio", { name: /Explorer/ }));
    fireEvent.click(screen.getByRole("radio", { name: /Custom/ }));

    // Seeded from the Explorer, which spends all 100 points and 10 stars.
    expect(screen.getByRole("button", { name: "Next" }).disabled).toBe(false);

    fireEvent.change(screen.getAllByLabelText("Drones")[0], { target: { value: "40" } });
    expect(screen.getByRole("button", { name: "Next" }).title).toBe("Spend all 100 unit points (10 left)");
    fireEvent.change(screen.getAllByLabelText("Drones")[0], { target: { value: "50" } });

    fireEvent.change(screen.getByLabelText("Race"), { target: { value: "" } });
    expect(screen.getByRole("button", { name: "Next" }).title).toBe("Choose a race");
    fireEvent.change(screen.getByLabelText("Race"), { target: { value: "Xo" } });

    next();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));
    await waitFor(() => expect(posted.length).toBe(1)); // no question: a custom kingdom has no plan
    expect(posted[0].body.race).toBe("Xo");
    expect(posted[0].body.kdName).toBe("Mine");
    expect(posted[0].body.unitsChoices.drones).toBe("50");
    await settled();
});

test("a kingdom that already has a name skips the name step", async () => {
    renderPage({ kingdomid: { kd_id: "1", created: false } });
    await screen.findByText("How do you want to play?");
    expect(screen.queryByText("Name your kingdom")).toBeNull();

    fireEvent.click(screen.getByRole("radio", { name: /Explorer/ }));
    next();
    expect(screen.getByText("Taken Name")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));
    fireEvent.click(await screen.findByRole("button", { name: "Keep it off" }));

    await waitFor(() => expect(posted.length).toBe(1));
    expect(posted[0].body).toEqual({ preset: "explorer", autoBuilder: false });
    await settled();
});

test("a refusal is shown, and a bad name sends the player back to the name step", async () => {
    authFetch.mockImplementation((url) => (url === "api/createkingdomdata"
        ? respond(CREATOR)
        : respond({ message: "Kingdom name already exists", field: "name" }, false)));
    const updateData = renderPage();
    await screen.findByText("Name your kingdom");
    typeName("Fresh");
    next();
    fireEvent.click(screen.getByRole("radio", { name: /Explorer/ }));
    next();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));
    fireEvent.click(await screen.findByRole("button", { name: "Keep it off" }));

    expect(await screen.findByText("Kingdom name already exists")).toBeTruthy();
    expect(screen.getByText("Name your kingdom")).toBeTruthy();
    expect(updateData).not.toHaveBeenCalled();
});

test("a network failure is shown and the button works again", async () => {
    authFetch.mockImplementation((url) => (url === "api/createkingdomdata" ? respond(CREATOR) : Promise.reject(new Error("down"))));
    renderPage({ kingdomid: { kd_id: "1", created: false } });
    await screen.findByText("How do you want to play?");
    fireEvent.click(screen.getByRole("radio", { name: /Explorer/ }));
    next();
    fireEvent.click(screen.getByRole("button", { name: "Create kingdom" }));
    fireEvent.click(await screen.findByRole("button", { name: "Keep it off" }));

    expect(await screen.findByText("Could not reach the server, try again")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create kingdom" }).disabled).toBe(false);
});

test("a creator that will not load offers to try again", async () => {
    authFetch.mockImplementation(() => Promise.reject(new Error("down")));
    renderPage();
    expect(await screen.findByText("Could not load the kingdom creator.")).toBeTruthy();

    authFetch.mockImplementation(() => respond(CREATOR));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Name your kingdom")).toBeTruthy();
});
