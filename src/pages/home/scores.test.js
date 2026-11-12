import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Scores from "./scores";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);

const data = {
    kingdomid: { kd_id: "2" },
    kingdoms: { 1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta" },
    galaxies_inverted: { 1: "1:1", 2: "1:2", 3: "1:2", 4: "1:3" },
    scores: {
        points: [["1", 120.5], ["3", 80], ["2", 50.25], ["4", 10]],
        networth: [["2", 9000], ["1", 100]],
        stars: [["4", 400], ["1", 300]],
        galaxy_networth: [["1:2", 9500], ["1:1", 100]],
    },
};

test("the leaderboard lists kingdoms best first, with their galaxy", () => {
    render(<Scores data={data} />);
    const rows = screen.getAllByRole("row").slice(1, 5).map((row) => row.textContent);
    expect(rows[0]).toMatch(/1Alpha \(1:1\)120\.50/);
    expect(rows[2]).toMatch(/3Beta \(1:2\)50\.25/);
});

test("it says where you are, and marks your row and your galaxymates", () => {
    render(<Scores data={data} />);
    expect(screen.getByText("You are ranked 3 of 4. 29.75 more to pass Gamma (1:2).")).toBeTruthy();
    // every tab is on the page at once; the first is the points table
    const inPoints = (text) => screen.getAllByText(text)[0].closest("tr").className;
    expect(inPoints("Beta (1:2)")).toBe("scores-you");
    expect(inPoints("Gamma (1:2)")).toBe("scores-mate");
    expect(inPoints("Alpha (1:1)")).toBe("");
});

test("each tab has its own ranking", () => {
    render(<Scores data={data} />);
    fireEvent.click(screen.getByRole("tab", { name: "Networth" }));
    expect(screen.getAllByText("You are ranked 1 of 2. You are in the lead.").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("tab", { name: "Galaxy Networth" }));
    expect(screen.getAllByText("1:2")[0].closest("tr").className).toBe("scores-you");
});

test("no scores yet is an empty table, not a crash", () => {
    render(<Scores data={{ ...data, scores: undefined }} />);
    expect(screen.getAllByRole("table").length).toBeGreaterThan(0);
});
