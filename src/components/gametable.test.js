import React from "react";
import { render, screen, within } from "@testing-library/react";
import { GameTable } from "./gametable";

const columns = [
    { header: "Unit", align: "left", cell: (row) => row.name },
    { header: "Have", cell: (row) => row.have },
    { header: "To Train", phoneRow: true, cell: (row) => <input aria-label={`${row.name} to train`} /> },
];
const rows = [{ key: "a", name: "Attackers", have: 5 }, { key: "d", name: "Defenders", have: 7 }];

function asScreen(wide) {
    const original = window.matchMedia;
    window.matchMedia = (query) => ({ matches: wide, media: query, addEventListener: () => {}, removeEventListener: () => {} });
    return () => { window.matchMedia = original; };
}

test("on a wide screen a phoneRow column is an ordinary column", () => {
    const restore = asScreen(true);
    try {
        render(<GameTable columns={columns} rows={rows} />);
        expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Unit", "Have", "To Train"]);
        expect(screen.getAllByRole("row")).toHaveLength(3);
        const attackers = screen.getByRole("row", { name: /Attackers/ });
        expect(within(attackers).getByLabelText("Attackers to train")).toBeInTheDocument();
    } finally { restore(); }
});

test("on a phone a phoneRow column goes on its own line, across the whole row", () => {
    const restore = asScreen(false);
    try {
        render(<GameTable columns={columns} rows={rows} />);
        expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Unit", "Have"]);
        // A header row, then two lines for each unit.
        expect(screen.getAllByRole("row")).toHaveLength(5);
        const slider = screen.getByLabelText("Attackers to train");
        const cell = slider.closest("td");
        expect(cell.getAttribute("colspan")).toBe("2");
        expect(cell.closest("tr").previousSibling.textContent).toContain("Attackers");
        expect(screen.getAllByLabelText(/to train/)).toHaveLength(2);
    } finally { restore(); }
});
