import React from "react";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { AdvisorsList } from "./advisors";

const danger = {
    id: "out_of_fuel", kind: "danger", text: "Your kingdom is out of fuel.", hideable: true, hidden: false,
    links: [{ label: "Build fuel plants", to: "/structures" }, { label: "Shields", to: "/shields" }],
};
const waste = {
    id: "empty_stars", kind: "waste", text: "30 stars have nothing on them.", hideable: true, hidden: false,
    links: [{ label: "Build", to: "/structures" }],
};
const show = (answer, onHide = () => {}) =>
    render(<MemoryRouter><AdvisorsList answer={answer} onHide={onHide} /></MemoryRouter>);

test("each advice links to where it is fixed", () => {
    show({ enabled: true, advice: [danger] });
    expect(screen.getByText("Your kingdom is out of fuel.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Build fuel plants" }).getAttribute("href")).toBe("/structures");
    expect(screen.getByRole("link", { name: "Shields" }).getAttribute("href")).toBe("/shields");
});

test("every advice can be hidden, danger included", () => {
    const onHide = jest.fn();
    show({ enabled: true, advice: [danger, waste] }, onHide);
    const buttons = screen.getAllByRole("button", { name: "Hide" });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[0]);
    expect(onHide).toHaveBeenCalledWith("out_of_fuel", true);
});

test("hidden advice waits behind a toggle and can be shown again", () => {
    const onHide = jest.fn();
    show({ enabled: true, advice: [{ ...waste, hidden: true }] }, onHide);
    expect(screen.getByText("Your advisors have nothing to report.")).toBeTruthy();
    expect(screen.queryByText("30 stars have nothing on them.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show hidden advice (1)" }));
    expect(screen.getByText("30 stars have nothing on them.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show again" }));
    expect(onHide).toHaveBeenCalledWith("empty_stars", false);
});

test("advisors switched off say where to turn them on", () => {
    show({ enabled: false, advice: [] });
    expect(screen.getByRole("link", { name: "Turn them on in Settings." }).getAttribute("href")).toBe("/settings");
});

test("nothing to report when there is no advice", () => {
    show({ enabled: true, advice: [] });
    expect(screen.getByText("Your advisors have nothing to report.")).toBeTruthy();
});
