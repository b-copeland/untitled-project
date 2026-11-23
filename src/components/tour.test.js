import React from "react";
import fs from "fs";
import path from "path";
import { Link, MemoryRouter, useLocation } from "react-router-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { TourProvider, TourOffer, TourReminder, useTour } from "./tour";
import { TOUR_STOPS, demoTarget, tourLength, resolve } from "../tour";

jest.mock("../auth", () => ({ authFetch: jest.fn() }));
const { authFetch } = require("../auth");

const updateData = jest.fn();
beforeEach(() => {
    updateData.mockImplementation((keys, funcs) => funcs.forEach((f) => f()));
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success" }) }));
});

const saved = () => authFetch.mock.calls.map(([, options]) => JSON.parse(options.body).tour);

const STOPS = [
    { path: "/status", title: "First stop", text: "On the status page." },
    { path: ({ demo }) => `/attack?target=${demo}`, target: "here", title: "Second stop", text: ({ demoName }) => `Aiming at ${demoName}.` },
    { path: "/politics", title: "Last stop", text: "The end." },
];
const DATA = {
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Mine", 2: "Mate", 7: "Far", 5: "Near" },
    galaxies_inverted: { 1: "1:1", 2: "1:1", 7: "2:1", 5: "1:2" },
};

function Where() {
    const location = useLocation();
    return <div data-testid="where">{location.pathname + location.search}</div>;
}
function StartButton() {
    const { start } = useTour();
    return <button onClick={start}>start from settings</button>;
}

const show = (tour, start = "/galaxy") => render(
    <MemoryRouter initialEntries={[start]}>
        <TourProvider data={{ ...DATA, preferences: { tour } }} updateData={updateData} stops={STOPS}>
            <TourOffer />
            <TourReminder />
            <StartButton />
            <Where />
            <Link to="/news">wander off</Link>
            <div data-tour="here">the outlined part</div>
        </TourProvider>
    </MemoryRouter>
);

test("a new player is offered the tour with how long it takes, and Not now or closing it saves later", () => {
    show("offer");
    expect(screen.getByText(/It takes about \d+ minutes/)).toBeTruthy();
    fireEvent.click(screen.getByText("Not now"));
    expect(screen.queryByText("Take a quick tour?")).toBeNull();
    expect(saved()).toEqual(["later"]);
});

test("No thanks saves declined", () => {
    show("offer");
    fireEvent.click(screen.getByText("No thanks"));
    expect(saved()).toEqual(["declined"]);
});

test("once answered there is no offer", () => {
    for (const tour of ["later", "declined", "done", undefined]) {
        const { unmount } = show(tour);
        expect(screen.queryByText("Take a quick tour?")).toBeNull();
        unmount();
    }
});

test("the tour opens each stop's page, outlines its part, and finishing saves done", () => {
    show("offer");
    fireEvent.click(screen.getByText("Take the tour"));
    expect(screen.getByText("Stop 1 of 3")).toBeTruthy();
    expect(screen.getByTestId("where").textContent).toBe("/status");

    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByText("Second stop")).toBeTruthy();
    expect(screen.getByText("Aiming at Near.")).toBeTruthy();  // the example is the lowest kingdom of another galaxy
    expect(screen.getByTestId("where").textContent).toBe("/attack?target=5");
    expect(screen.getByText("the outlined part").hasAttribute("data-tour-active")).toBe(true);

    fireEvent.click(screen.getByText("Back"));
    expect(screen.getByTestId("where").textContent).toBe("/status");
    expect(screen.getByText("the outlined part").hasAttribute("data-tour-active")).toBe(false);

    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Next"));
    expect(screen.getByTestId("where").textContent).toBe("/politics");
    fireEvent.click(screen.getByText("Finish"));
    expect(screen.queryByText("Last stop")).toBeNull();
    expect(saved()).toEqual(["done"]);
});

test("leaving early saves later, so the Status page keeps its reminder", () => {
    show("offer");
    fireEvent.click(screen.getByText("Take the tour"));
    fireEvent.click(screen.getByLabelText("End the tour"));
    expect(screen.queryByText("First stop")).toBeNull();
    expect(saved()).toEqual(["later"]);
});

test("a player who finished or declined can take it again from Settings without the reminder coming back", () => {
    show("done");
    fireEvent.click(screen.getByText("start from settings"));
    expect(screen.getByText("First stop")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("End the tour"));
    expect(authFetch).not.toHaveBeenCalled();
});

test("a player who wanders off during a stop can go back to it", () => {
    show("later", "/status");
    fireEvent.click(screen.getByText("Take the tour"));  // the reminder's button
    expect(screen.queryByText("Back to this stop")).toBeNull();
    fireEvent.click(screen.getByText("wander off"));
    expect(screen.getByTestId("where").textContent).toBe("/news");
    fireEvent.click(screen.getByText("Back to this stop"));
    expect(screen.getByTestId("where").textContent).toBe("/status");
});

test("the reminder shows only after Not now, and its No thanks saves declined", () => {
    show("later");
    expect(screen.getByText("Guided tour")).toBeTruthy();
    fireEvent.click(screen.getByText("No thanks"));
    expect(saved()).toEqual(["declined"]);
    const { container } = show("done");
    expect(container.querySelector(".tour-reminder")).toBeNull();
});

test("the example kingdom is from another galaxy, or there is none", () => {
    expect(demoTarget(DATA)).toBe("5");
    expect(demoTarget({ ...DATA, kingdoms: { 1: "Mine", 2: "Mate" } })).toBeUndefined();
    expect(demoTarget({})).toBeUndefined();
});

test("the length is worked out from the stops", () => {
    expect(tourLength(STOPS)).toBe("about 1 minute");
    expect(tourLength(TOUR_STOPS)).toMatch(/^about \d+ minutes$/);
});

/** Every .js file under src/, except the tour's own. */
function sources(dir = path.join(__dirname, "..")) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) return sources(full);
        return entry.name.endsWith(".js") && !entry.name.endsWith(".test.js") && !full.endsWith(path.join("src", "tour.js"))
            ? [fs.readFileSync(full, "utf8")] : [];
    });
}

test("every stop has words and a page, and each part it outlines is marked on some page", () => {
    const code = sources().join("\n");
    const context = { demo: "5", demoName: "Near" };
    for (const stop of TOUR_STOPS) {
        expect(resolve(stop.path, context)).toMatch(/^\//);
        expect(stop.title).toBeTruthy();
        expect(resolve(stop.text, context)).toBeTruthy();
        expect(resolve(stop.text, context)).not.toMatch(/epoch/i);
        if (stop.target) {
            const marked = code.includes(`data-tour="${stop.target}"`) || code.includes(`tour="${stop.target}"`);
            expect([stop.target, marked]).toEqual([stop.target, true]);
        }
    }
});
