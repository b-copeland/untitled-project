import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import Universe, { COLORS, NO_EMPIRE, OTHER_COLOR, colorsFor, galaxyRows, grouping, layout } from "./universe";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);

const galaxies = { "1:1": ["1", "2"], "1:2": ["3"], "2:1": ["4", "5", "6"], "1:10": [] };
const empires = { 0: { name: "Red Empire", galaxies: ["1:1", "2:1"] }, 1: { name: "Blue Empire", galaxies: ["1:2"] } };
const scores = {
    galaxy_networth: [["2:1", 900], ["1:1", 300], ["1:2", 100]],
    galaxy_kingdoms_alive: { "1:1": 2, "1:2": 1, "2:1": 2 },  // one of 2:1's three kingdoms is dead
};

const data = {
    galaxies,
    empires,
    scores,
    galaxies_inverted: { 1: "1:1" },
    kingdomid: { kd_id: "1" },
};

const inside = (inner, outer) => Math.hypot(inner.x - outer.x, inner.y - outer.y) + inner.r <= outer.r + 1e-6;
const fillOf = (galaxy) => screen.getByTestId(`galaxy-${galaxy}`).querySelector("circle").getAttribute("fill");

test("rows come in cluster and galaxy order, counting only kingdoms alive", () => {
    const rows = galaxyRows(galaxies, empires, scores);
    expect(rows.map((row) => row.galaxy)).toEqual(["1:1", "1:2", "1:10", "2:1"]);
    expect(rows[0]).toMatchObject({ cluster: "1", kingdoms: 2, networth: 300, empire: "0" });
    expect(rows[2]).toMatchObject({ kingdoms: 0, networth: 0, empire: null });
    expect(rows[3].kingdoms).toBe(2);
});

test("before the refresh has counted kingdoms alive, every kingdom counts", () => {
    const rows = galaxyRows(galaxies, empires, { galaxy_networth: [] });
    expect(rows.find((row) => row.galaxy === "2:1").kingdoms).toBe(3);
});

test.each(["cluster", "empire"])("grouped by %s, every galaxy sits inside its group and area follows its size", (groupBy) => {
    const rows = galaxyRows(galaxies, empires, scores);
    const groups = grouping(groupBy, rows, empires);
    const { groups: outer, galaxies: circles } = layout(rows, "networth", groups);
    const byGroup = Object.fromEntries(outer.map((group) => [group.group, group]));
    circles.forEach((circle) => expect(inside(circle, byGroup[groups.groupOf(circle)])).toBe(true));
    const radius = Object.fromEntries(circles.map((circle) => [circle.galaxy, circle.r]));
    expect(radius["2:1"] / radius["1:2"]).toBeCloseTo(3, 0);  // 900 against 100
    expect(radius["1:10"]).toBeGreaterThan(0);  // an empty galaxy is still on the chart
});

test("by empire, the groups are the empires in id order with galaxies in no empire last", () => {
    const rows = galaxyRows(galaxies, empires, scores);
    const groups = grouping("empire", rows, empires);
    expect(layout(rows, "kingdoms", groups).groups.map((group) => group.group)).toEqual(["0", "1", NO_EMPIRE]);
    expect(groups.groupLabel("0")).toBe("Red Empire");
    expect(groups.groupLabel(NO_EMPIRE)).toBe("No empire");
});

test("colours go by id, and the ninth and later share one", () => {
    const colors = colorsFor([...Array(10).keys()].map(String));
    expect(colors["0"]).toBe(COLORS[0]);
    expect(colors["7"]).toBe(COLORS[7]);
    expect(colors["9"]).toBe(OTHER_COLOR);
    expect(colorsFor(["0", "1", "2", "4"])["2"]).toBe(colors["2"]);
});

test("by cluster, galaxies are coloured by empire, yours is ringed, and pointing names one", () => {
    render(<Universe data={data} loading={{}} updateData={jest.fn()} />);
    expect(fillOf("1:1")).toBe(COLORS[0]);
    expect(fillOf("1:2")).toBe(COLORS[1]);
    expect(fillOf("1:10")).toBe("none");
    expect(screen.getByTestId("galaxy-1:1").querySelector("circle").getAttribute("class")).toContain("universe-mine");
    fireEvent.mouseEnter(screen.getByTestId("galaxy-2:1"));
    expect(screen.getByText(/Galaxy 2:1 · Cluster 2 · 2 kingdoms alive · networth 900 · Red Empire/, { selector: "p" })).toBeTruthy();
    const legend = within(screen.getByRole("list", { name: "Colours" }));
    expect(legend.getByText("Red Empire")).toBeTruthy();
    expect(legend.getByText("No empire")).toBeTruthy();
});

test("by empire, galaxies are coloured by cluster and the legend lists clusters", () => {
    render(<Universe data={data} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByLabelText("By empire"));
    expect(screen.getByRole("heading", { name: "Galaxies by empire" })).toBeTruthy();
    expect(fillOf("1:1")).toBe(COLORS[0]);
    expect(fillOf("1:10")).toBe(COLORS[0]);  // cluster 1, in no empire
    expect(fillOf("2:1")).toBe(COLORS[1]);
    const legend = within(screen.getByRole("list", { name: "Colours" }));
    expect(legend.getByText("Cluster 2")).toBeTruthy();
    expect(screen.getByText("Blue Empire", { selector: "text" })).toBeTruthy();
});

test("the table lists every galaxy", () => {
    render(<Universe data={data} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByLabelText("Table"));
    const row = screen.getByText("1:1 (yours)").closest("tr");
    expect(within(row).getByText("Red Empire")).toBeTruthy();
    expect(screen.getAllByRole("row")).toHaveLength(5);  // the header and four galaxies
});

test("a phone starts on the table", () => {
    const original = window.matchMedia;
    window.matchMedia = (query) => ({ matches: false, media: query, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
    try {
        render(<Universe data={data} loading={{}} updateData={jest.fn()} />);
        expect(screen.getByText("1:1 (yours)")).toBeTruthy();
        expect(screen.queryByTestId("galaxy-1:1")).toBeNull();
    } finally {
        window.matchMedia = original;
    }
});

test("a universe with no galaxies says so", () => {
    render(<Universe data={{ ...data, galaxies: {} }} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText("There are no galaxies yet.")).toBeTruthy();
});
