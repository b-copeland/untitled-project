import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Structures from "./structures";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));

const zero = { homes: 0, mines: 0, fuel_plants: 0, hangars: 0, drone_factories: 0, missile_silos: 0, workshops: 0 };
const data = {
    structures: {
        current: { ...zero, homes: 100 }, hour_24: zero, price: 50, max_available_structures: 30, current_available_structures: 20,
    },
    kingdom: { stars: 300, structures: { ...zero, homes: 100 }, structures_target: { ...zero, homes: 0.6, mines: 0.3 } },
    state: { game_config: {}, pretty_names: {} },
};

let updateData;
beforeEach(() => { updateData = jest.fn(); });

const renderStructures = () => render(<Structures data={data} loading={{}} updateData={updateData} />);
const button = (name) => screen.getByRole("button", { name });

test("Build is disabled until something is entered", () => {
    renderStructures();
    expect(button("Build").disabled).toBe(true);
    fireEvent.change(document.getElementById("homes-input"), { target: { name: "homes", value: "5" } });
    expect(button("Build").disabled).toBe(false);
});

test("asking for more than is available says so, and blocks the button", () => {
    renderStructures();
    fireEvent.change(document.getElementById("mines-input"), { target: { name: "mines", value: "25" } });

    expect(screen.getAllByText("At most 20").length).toBeGreaterThan(0);
    expect(button("Build").disabled).toBe(true);
});

test("each field can be fine while the total is too much", () => {
    renderStructures();
    fireEvent.change(document.getElementById("homes-input"), { target: { name: "homes", value: "15" } });
    fireEvent.change(document.getElementById("mines-input"), { target: { name: "mines", value: "10" } });

    expect(screen.queryByText("At most 20")).toBeNull();
    expect(button("Build").disabled).toBe(true);
    expect(button("Build").title).toMatch(/Total 25 is over the limit of 20/);
});

test("a valid build is sent with the values typed, then the form is cleared", () => {
    renderStructures();
    fireEvent.change(document.getElementById("homes-input"), { target: { name: "homes", value: "7" } });
    fireEvent.click(button("Build"));

    expect(updateData).toHaveBeenCalledWith(["structures", "kingdom"], [expect.any(Function)]);
    expect(document.getElementById("homes-input").value).toBe("");
});

test("allocation over 100% is refused before sending", () => {
    renderStructures();
    fireEvent.click(screen.getByRole("tab", { name: "Allocate" }));
    const input = document.querySelector('#controlled-tab-example-tabpane-allocate input[name="workshops"]');
    fireEvent.change(input, { target: { name: "workshops", value: "20" } });  // 60% + 30% already allocated

    expect(screen.getByText(/Allocation after this change: 110.0%/)).toBeTruthy();
    expect(button("Update").disabled).toBe(true);
});

test("razing more than you have is refused", () => {
    renderStructures();
    fireEvent.click(screen.getByRole("tab", { name: "Raze" }));
    const input = document.getElementById("raze-homes");
    fireEvent.change(input, { target: { name: "homes", value: "101" } });

    expect(screen.getByText("At most 100")).toBeTruthy();
    expect(button("Raze").disabled).toBe(true);
});
