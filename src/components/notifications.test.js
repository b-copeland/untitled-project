import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Notifications } from "./notifications";

const message = { category: "Attack", status: "warning", message: "You were attacked by Realm 7", delay: 60000 };

beforeEach(() => {
    Object.assign(navigator, { clipboard: { writeText: jest.fn(() => Promise.resolve()) } });
});

test("clicking a notification copies its text and says so", async () => {
    render(<Notifications messages={[message]} dismiss={() => {}} />);

    fireEvent.click(screen.getByText("You were attacked by Realm 7"));

    await waitFor(() => screen.getByText("Copied"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("You were attacked by Realm 7");
});

test("selecting the text by hand is not a click to copy", () => {
    window.getSelection = () => ({ toString: () => "attacked" });
    render(<Notifications messages={[message]} dismiss={() => {}} />);

    fireEvent.click(screen.getByText("You were attacked by Realm 7"));

    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
});

test("closing one notification removes only that one", () => {
    const dismiss = jest.fn();
    render(<Notifications messages={[message, { ...message, message: "second" }]} dismiss={dismiss} />);

    fireEvent.click(screen.getAllByLabelText("Close")[1]);

    expect(dismiss).toHaveBeenCalledWith(1);
});
