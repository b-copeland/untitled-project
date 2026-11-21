import React from "react";
import { render as renderBare, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Scores from "./scores";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);

const render = (element) => renderBare(<MemoryRouter>{element}</MemoryRouter>);

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

// One leaderboard's card, by its title.
const board = (title) => within(screen.getByRole("heading", { name: title }).closest("section"));

test("the leaderboard lists kingdoms best first, with their galaxy, each linking to its page", () => {
    render(<Scores data={data} />);
    const rows = board("Points").getAllByRole("row").slice(1).map((row) => row.textContent);
    expect(rows[0]).toMatch(/1Alpha \(1:1\)120\.50/);
    expect(rows[2]).toMatch(/3Beta \(1:2\)50\.25/);
    expect(board("Points").getByRole("link", { name: "Alpha (1:1)" }).getAttribute("href")).toBe("/kingdom/1");
});

test("it says where you are, and marks your row and your galaxymates", () => {
    render(<Scores data={data} />);
    expect(board("Points").getByText("You are ranked 3 of 4.")).toBeTruthy();
    const rowOf = (text) => board("Points").getByText(text).closest("tr").className;
    expect(rowOf("Beta (1:2)")).toBe("scores-you");
    expect(rowOf("Gamma (1:2)")).toBe("scores-mate");
    expect(rowOf("Alpha (1:1)")).toBe("");
});

test("each leaderboard has its own ranking, and galaxies link to the Galaxy page", () => {
    render(<Scores data={data} />);
    expect(board("Networth").getByText("You are ranked 1 of 2.")).toBeTruthy();
    const galaxy = board("Galaxy networth").getByRole("link", { name: "1:2" });
    expect(galaxy.closest("tr").className).toBe("scores-you");
    expect(galaxy.getAttribute("href")).toBe("/galaxy?galaxy=1%3A2");
});

test("a long leaderboard shows the top ten and your row, until Show all", () => {
    const many = Array.from({ length: 15 }, (_, index) => [String(index + 10), 100 - index]);
    const kingdoms = Object.fromEntries(many.map(([id]) => [id, "K" + id]));
    render(<Scores data={{ ...data, kingdomid: { kd_id: "23" }, kingdoms, scores: { ...data.scores, points: many } }} />);
    expect(board("Points").getAllByRole("row").length).toBe(1 + 10 + 1);
    expect(board("Points").getByText("K23 (?)").closest("tr").className).toBe("scores-you scores-gap");
    fireEvent.click(board("Points").getByRole("button", { name: "Show all 15" }));
    expect(board("Points").getAllByRole("row").length).toBe(1 + 15);
});

test("no scores yet is an empty table, not a crash", () => {
    render(<Scores data={{ ...data, scores: undefined }} />);
    expect(screen.getAllByRole("table").length).toBe(4);
});
