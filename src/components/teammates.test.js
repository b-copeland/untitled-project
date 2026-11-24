import React from "react";
import { render, screen } from "@testing-library/react";
import { teamOf, targetOptions, TeammateWarning } from "./teammates";

const data = {
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Me", 2: "Mate", 3: "Ally", 4: "Stranger" },
    galaxies_inverted: { 1: "1:1", 2: "1:1", 3: "1:2", 4: "2:1" },
    empires_inverted: { empires_inverted: { 1: "e1", 2: "e1", 3: "e1", 4: "e2" } },
};

test("a galaxymate is in the galaxy, another galaxy of the empire is in the empire, the rest are neither", () => {
    expect(teamOf(data, "2")).toBe("galaxy");
    expect(teamOf(data, "3")).toBe("empire");
    expect(teamOf(data, "4")).toBe(null);
    expect(teamOf(data, "1")).toBe(null);
    expect(teamOf(data, undefined)).toBe(null);
});

test("without an empire, only galaxymates count", () => {
    const loner = { ...data, empires_inverted: { empires_inverted: { 3: "e1" } } };
    expect(teamOf(loner, "2")).toBe("galaxy");
    expect(teamOf(loner, "3")).toBe(null);
});

test("the options leave out your own kingdom and carry each one's team", () => {
    expect(targetOptions(data)).toEqual([
        { value: "2", label: "Mate (1:1)", team: "galaxy" },
        { value: "3", label: "Ally (1:2)", team: "empire" },
        { value: "4", label: "Stranger (2:1)", team: null },
    ]);
});

test("the warning shows only for a teammate", () => {
    const { rerender } = render(<TeammateWarning data={data} target="2" doing="Attacking them" />);
    expect(screen.getByText(/Mate is in your galaxy/)).toBeTruthy();
    expect(screen.getByText(/Attacking them hurts your own team/)).toBeTruthy();
    rerender(<TeammateWarning data={data} target="4" doing="Attacking them" />);
    expect(screen.queryByText(/hurts your own team/)).toBeNull();
});
