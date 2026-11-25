import React from "react";
import fs from "fs";
import path from "path";
import { render, screen, fireEvent } from "@testing-library/react";
import { KingdomPicker } from "./kingdompicker";

const data = {
    kingdomid: { kd_id: "1" },
    kingdoms: { 1: "Me", 2: "Mate", 3: "Ally", 4: "Stranger" },
    galaxies_inverted: { 1: "1:1", 2: "1:1", 3: "1:2", 4: "2:1" },
    empires_inverted: { empires_inverted: { 1: "e1", 2: "e1", 3: "e1" } },
};

const open = () => fireEvent.keyDown(document.getElementById("pick"), { key: "ArrowDown" });

test("every kingdom but yours is offered, teammates tagged", () => {
    render(<KingdomPicker id="pick" data={data} onChange={jest.fn()} />);
    open();
    expect(screen.queryByText("Me (1:1)")).toBeNull();
    expect(screen.getByText("Mate (1:1)")).toBeTruthy();
    expect(screen.getByText("Your galaxy")).toBeTruthy();
    expect(screen.getByText("Your empire")).toBeTruthy();
    expect(screen.getByText("Stranger (2:1)")).toBeTruthy();
});

test("only limits the list", () => {
    render(<KingdomPicker id="pick" data={data} only={["4"]} onChange={jest.fn()} />);
    open();
    expect(screen.queryByText("Mate (1:1)")).toBeNull();
    expect(screen.getByText("Stranger (2:1)")).toBeTruthy();
});

test("a teammate warns only where the page would harm them", () => {
    const { rerender } = render(<KingdomPicker id="pick" data={data} value="2" onChange={jest.fn()} harm="Siphoning their income" />);
    expect(screen.getByText(/Siphoning their income hurts your own team/)).toBeTruthy();
    rerender(<KingdomPicker id="pick" data={data} value="2" onChange={jest.fn()} />);
    expect(screen.queryByText(/hurts your own team/)).toBeNull();
    rerender(<KingdomPicker id="pick" data={data} value="4" onChange={jest.fn()} harm="Attacking them" />);
    expect(screen.queryByText(/hurts your own team/)).toBeNull();
});

test("no page builds its own list of kingdoms to pick from: they all use KingdomPicker", () => {
    const pages = path.join(__dirname, "..", "pages");
    const files = [];
    const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.name.endsWith(".js") && !entry.name.endsWith(".test.js")) files.push(full);
    });
    walk(pages);
    // A picker option built from a kingdom id ({ value: kdId, label: ... }) is a hand-made kingdom list.
    const offenders = files.filter((file) => /\{\s*value:\s*kdId\s*,\s*label:/.test(fs.readFileSync(file, "utf8")));
    expect(offenders.map((file) => path.relative(pages, file))).toEqual([]);
});
