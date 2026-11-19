import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import UniverseMap, { EMPIRE_COLORS, OTHER_EMPIRE, empireColors, galaxyRows, layout } from "./universemap";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);

const galaxies = { "1:1": ["1", "2"], "1:2": ["3"], "2:1": ["4", "5", "6"], "1:10": [] };
const empires = { 0: { name: "Red Empire", galaxies: ["1:1", "2:1"] } };
const galaxyNetworth = [["2:1", 900], ["1:1", 300], ["1:2", 100]];

const data = {
    galaxies,
    empires,
    scores: { galaxy_networth: galaxyNetworth },
    galaxies_inverted: { 1: "1:1" },
    kingdomid: { kd_id: "1" },
};

const inside = (inner, outer) => Math.hypot(inner.x - outer.x, inner.y - outer.y) + inner.r <= outer.r + 1e-6;

test("rows come in cluster and galaxy order, with public numbers only", () => {
    const rows = galaxyRows(galaxies, empires, galaxyNetworth);
    expect(rows.map((row) => row.galaxy)).toEqual(["1:1", "1:2", "1:10", "2:1"]);
    expect(rows[0]).toMatchObject({ cluster: "1", kingdoms: 2, networth: 300, empire: "0" });
    expect(rows[2]).toMatchObject({ kingdoms: 0, networth: 0, empire: null });
});

test("every galaxy sits inside its cluster, and bigger ones are bigger", () => {
    const rows = galaxyRows(galaxies, empires, galaxyNetworth);
    const { clusters, galaxies: circles } = layout(rows, "kingdoms");
    expect(clusters.map((cluster) => cluster.cluster)).toEqual(["1", "2"]);
    const clusterOf = Object.fromEntries(clusters.map((cluster) => [cluster.cluster, cluster]));
    circles.forEach((circle) => expect(inside(circle, clusterOf[circle.cluster])).toBe(true));
    const radius = Object.fromEntries(circles.map((circle) => [circle.galaxy, circle.r]));
    expect(radius["2:1"]).toBeGreaterThan(radius["1:1"]);
    expect(radius["1:10"]).toBeGreaterThan(0);  // an empty galaxy is still on the map
    const byNetworth = Object.fromEntries(layout(rows, "networth").galaxies.map((circle) => [circle.galaxy, circle.r]));
    expect(byNetworth["2:1"] / byNetworth["1:2"]).toBeCloseTo(3, 0);  // area follows networth: 900 / 100
});

test("an empire keeps its colour by id, and the ninth and later share one", () => {
    const many = Object.fromEntries([...Array(10).keys()].map((i) => [String(i), { name: `E${i}`, galaxies: [] }]));
    const colors = empireColors(many);
    expect(colors["0"]).toBe(EMPIRE_COLORS[0]);
    expect(colors["7"]).toBe(EMPIRE_COLORS[7]);
    expect(colors["9"]).toBe(OTHER_EMPIRE);
    const { 3: _, ...fewer } = many;
    expect(empireColors(fewer)["2"]).toBe(colors["2"]);
});

test("the map colours galaxies by empire, rings yours and names what you point at", () => {
    render(<UniverseMap data={data} loading={{}} updateData={jest.fn()} />);
    const mine = screen.getByTestId("galaxy-1:1");
    expect(mine.querySelector("circle").getAttribute("fill")).toBe(EMPIRE_COLORS[0]);
    expect(mine.querySelector("circle").getAttribute("class")).toContain("universe-map-mine");
    expect(screen.getByTestId("galaxy-1:2").querySelector("circle").getAttribute("fill")).toBe("none");
    fireEvent.mouseEnter(screen.getByTestId("galaxy-2:1"));
    expect(screen.getByText(/Galaxy 2:1 · Cluster 2 · 3 kingdoms · networth 900 · Red Empire/, { selector: "p" })).toBeTruthy();
    expect(within(screen.getByRole("list", { name: "Empires" })).getByText("Red Empire")).toBeTruthy();
    expect(screen.getByText("No empire")).toBeTruthy();
});

test("the table lists every galaxy", () => {
    render(<UniverseMap data={data} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByLabelText("Table"));
    const row = screen.getByText("1:1 (yours)").closest("tr");
    expect(within(row).getByText("Red Empire")).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(5);  // the header and four galaxies
});

test("a phone starts on the table", () => {
    const original = window.matchMedia;
    window.matchMedia = (query) => ({ matches: false, media: query, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
    try {
        render(<UniverseMap data={data} loading={{}} updateData={jest.fn()} />);
        expect(screen.getByText("1:1 (yours)")).toBeTruthy();
        expect(screen.queryByTestId("galaxy-1:1")).toBeNull();
    } finally {
        window.matchMedia = original;
    }
});

test("a universe with no galaxies says so", () => {
    render(<UniverseMap data={{ ...data, galaxies: {} }} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("There are no galaxies yet.")).toBeTruthy();
});
