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
    kingdom: { stars: 300, money: 100000, structures: { ...zero, homes: 100 }, structures_target: { ...zero, homes: 0.6, mines: 0.3 } },
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

test("the sliders stop at what is available, and the second is capped by what the first leaves", () => {
    renderStructures();
    fireEvent.change(document.getElementById("mines-input"), { target: { name: "mines", value: "25" } });
    expect(document.getElementById("mines-input").value).toBe("20");       // 20 available

    fireEvent.change(document.getElementById("mines-input"), { target: { name: "mines", value: "0" } });
    fireEvent.change(document.getElementById("homes-input"), { target: { name: "homes", value: "15" } });
    fireEvent.change(document.getElementById("mines-input"), { target: { name: "mines", value: "10" } });
    expect(document.getElementById("mines-input").value).toBe("5");        // 15 + 5 = 20
    expect(button("Build").disabled).toBe(false);
});

test("a valid build is sent with the values typed, then the form is cleared", () => {
    renderStructures();
    fireEvent.change(document.getElementById("homes-input"), { target: { name: "homes", value: "7" } });
    fireEvent.click(button("Build"));

    expect(updateData).toHaveBeenCalledWith(["structures", "kingdom"], [expect.any(Function)]);
    expect(document.getElementById("homes-input").value).toBe("0");
});

test("an allocation can only go as far as is left of 100%", () => {
    renderStructures();
    fireEvent.click(screen.getByRole("tab", { name: "Allocate" }));
    const sliders = document.querySelectorAll('#controlled-tab-example-tabpane-allocate input[type="range"]');
    const workshops = sliders[sliders.length - 1];
    fireEvent.change(workshops, { target: { value: "20" } });  // 60% + 30% already allocated leaves 10%

    expect(workshops.value).toBe("10");
    expect(screen.getByText(/Allocation after this change: 100.0%/)).toBeTruthy();
    expect(button("Update").disabled).toBe(false);
});

test("razing cannot go past what you have", () => {
    renderStructures();
    fireEvent.click(screen.getByRole("tab", { name: "Raze" }));
    const input = document.getElementById("raze-homes");
    fireEvent.change(input, { target: { name: "homes", value: "101" } });

    expect(input.value).toBe("100");
    expect(button("Raze").disabled).toBe(false);
});
