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
