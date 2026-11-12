import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AmountInput } from "./forms";

function Harness({ max, error }) {
    const [value, setValue] = useState("");
    return <AmountInput name="homes" label="Homes" value={value} max={max} error={error} onChange={(e) => setValue(e.target.value)} />;
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
        return <AmountInput name="homes" label="Homes" value={value} max={available} soloMax={100} onChange={(e) => setValue(e.target.value)} />;
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
        return <AmountInput name="homes" label="Homes" value={value} max={60} soloMax={100} onChange={(e) => setValue(e.target.value)} />;
    }
    render(<Shared />);
    const style = screen.getByLabelText("Homes slider").style;
    expect(style.getPropertyValue("--val")).toBe("25%");
    expect(style.getPropertyValue("--avail")).toBe("60%");
});
