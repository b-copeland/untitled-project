import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import Settle from "./settle";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));

const data = { settle: { settle_time: 7200, settle_price: 400, max_available_settle: 50, current_available_settle: 30 } };
const type = (value) => fireEvent.change(document.getElementById("settle-input"), { target: { value } });
const settle = () => screen.getByRole("button", { name: "Settle" });

test("the button waits for a number", () => {
    render(<Settle data={data} loading={{}} updateData={jest.fn()} />);
    expect(settle().disabled).toBe(true);
    type("10");
    expect(settle().disabled).toBe(false);
    expect(screen.getByText("Settle Cost: 4,000")).toBeTruthy();
});

test.each([["31", "At most 30 stars"], ["-2", "Enter a whole number, 0 or more"], ["x", "Enter a whole number, 0 or more"]])(
    "%s is refused with a reason before it is sent", (value, reason) => {
        render(<Settle data={data} loading={{}} updateData={jest.fn()} />);
        type(value);
        expect(screen.getByText(reason)).toBeTruthy();
        expect(settle().disabled).toBe(true);
    });

test("zero is not a settlement", () => {
    render(<Settle data={data} loading={{}} updateData={jest.fn()} />);
    type("0");
    expect(settle().disabled).toBe(true);
});

test("a valid request is sent and the box emptied", () => {
    const updateData = jest.fn();
    render(<Settle data={data} loading={{}} updateData={updateData} />);
    type("12");
    fireEvent.click(settle());

    expect(updateData).toHaveBeenCalledWith(["settle", "kingdom"], [expect.any(Function)]);
    expect(document.getElementById("settle-input").value).toBe("");
});
