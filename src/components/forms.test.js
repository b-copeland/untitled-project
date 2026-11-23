import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AmountInput, NumberControl, NumberField, withoutCommas } from "./forms";

function Harness({ max, error, box = true }) {
    const [value, setValue] = useState("");
    return <AmountInput box={box} name="homes" label="Homes" value={value} max={max} error={error} onChange={(e) => setValue(e.target.value)} />;
}

test("Max fills in the most that can be done", () => {
    render(<Harness max={42} />);
    fireEvent.click(screen.getByRole("button", { name: "Max" }));
    expect(screen.getByLabelText("Homes").value).toBe("42");
});

test("the slider sets the box and the box moves the slider", () => {
    render(<Harness max={10} />);
    fireEvent.change(screen.getByLabelText("Homes slider"), { target: { value: "7" } });
    expect(screen.getByLabelText("Homes").value).toBe("7");
    fireEvent.change(screen.getByLabelText("Homes"), { target: { value: "3" } });
    expect(screen.getByLabelText("Homes slider").value).toBe("3");
});

test("with nothing to do the slider and Max are off, and an error shows", () => {
    render(<Harness max={0} error="Nope" />);
    expect(screen.getByRole("button", { name: "Max" }).disabled).toBe(true);
    expect(screen.getByLabelText("Homes slider").disabled).toBe(true);
    expect(screen.getByText("Nope")).toBeTruthy();
});

test("a max that is not a number does not break the slider", () => {
    render(<Harness max={NaN} />);
    expect(screen.getByLabelText("Homes slider").disabled).toBe(true);
});

test("the slider keeps its length when others use the pool, greys the lost part and stops there", () => {
    function Shared({ available }) {
        const [value, setValue] = useState("");
        return <AmountInput box name="homes" label="Homes" value={value} max={available} soloMax={100} onChange={(e) => setValue(e.target.value)} />;
    }
    render(<Shared available={40} />);
    const slider = screen.getByLabelText("Homes slider");
    expect(slider.max).toBe("100");                           // always the full, solo length
    expect(slider.style.getPropertyValue("--avail")).toBe("40%");  // 60% of it greyed out
    fireEvent.change(slider, { target: { value: "90" } });
    expect(screen.getByLabelText("Homes").value).toBe("40");  // the thumb stops at the grey line
    fireEvent.click(screen.getByRole("button", { name: "Max" }));
    expect(screen.getByLabelText("Homes").value).toBe("40");
});

test("the slider is dark up to the choice, light up to what is free, grey after", () => {
    function Shared() {
        const [value, setValue] = useState("25");
        return <AmountInput box name="homes" label="Homes" value={value} max={60} soloMax={100} onChange={(e) => setValue(e.target.value)} />;
    }
    render(<Shared />);
    const style = screen.getByLabelText("Homes slider").style;
    expect(style.getPropertyValue("--val")).toBe("25%");
    expect(style.getPropertyValue("--avail")).toBe("60%");
});

test("by default it is the slider alone: the number on its left, the most on its right, and no box", () => {
    render(<Harness max={10} box={false} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    const slider = screen.getByLabelText("Homes");
    expect(slider.type).toBe("range");
    fireEvent.change(slider, { target: { value: "7" } });
    expect(screen.getByText("7")).toBeTruthy();
    expect(slider.value).toBe("7");
});

test("pressing the most on its right fills it in", () => {
    render(<Harness max={42} box={false} />);
    fireEvent.click(screen.getByRole("button", { name: "42" }));
    expect(screen.getByLabelText("Homes").value).toBe("42");
});

test("the slider-only form shows an error and is off when there is nothing to do", () => {
    render(<Harness max={0} box={false} error="Nope" />);
    expect(screen.getByLabelText("Homes").disabled).toBe(true);
    expect(screen.getByRole("button", { name: "0" }).disabled).toBe(true);
    expect(screen.getByText("Nope")).toBeTruthy();
});

test("thousands separators are taken out of a number", () => {
    expect(withoutCommas("1,000,000")).toBe("1000000");
    expect(withoutCommas("2.5")).toBe("2.5");
    expect(withoutCommas(undefined)).toBe(undefined);
});

test("a typed or pasted 1,000 reaches the form as 1000 in every kind of number box", () => {
    render(<Harness max={5000} />);
    fireEvent.change(screen.getByLabelText("Homes"), { target: { value: "1,000" } });
    expect(screen.getByLabelText("Homes").value).toBe("1000");
    expect(screen.getByLabelText("Homes slider").value).toBe("1000");

    const seen = [];
    render(<NumberControl aria-label="Cut" name="cut" onChange={(e) => seen.push([e.target.name, e.target.value])} />);
    fireEvent.change(screen.getByLabelText("Cut"), { target: { value: "12,5" } });
    expect(seen).toEqual([["cut", "125"]]);

    const fieldSeen = [];
    render(<NumberField name="drones" onChange={(e) => fieldSeen.push(e.target.value)} />);
    fireEvent.change(document.getElementById("drones-input"), { target: { value: "2,500" } });
    expect(fieldSeen).toEqual(["2500"]);
});

test("the slider's numbers are short, with the exact number on hover", () => {
    render(<AmountInput name="money" label="Money" value="33123" max={2500000} onChange={() => {}} />);
    const value = screen.getByText("33k");
    expect(value).toHaveAttribute("title", "33,123");
    expect(screen.getByRole("button", { name: "2.5m" })).toHaveAttribute("title", "Fill in the most you can: 2,500,000");
});
