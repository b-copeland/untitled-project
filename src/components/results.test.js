import React, { useState } from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ResultToasts } from "./results";

function Page({ initial }) {
    const [results, setResults] = useState(initial);
    return <ResultToasts title="Settle" results={results} setResults={setResults} />;
}

afterEach(() => jest.useRealTimers());

test("a result that worked closes itself; one that did not stays until closed", () => {
    jest.useFakeTimers();
    render(<Page initial={[{ status: "success", message: "Settled 5 stars" }, { message: "Not enough money" }]} />);
    expect(screen.getByText("Settled 5 stars")).toBeTruthy();

    act(() => jest.advanceTimersByTime(7000));
    expect(screen.queryByText("Settled 5 stars")).toBeNull();
    expect(screen.getByRole("alert").textContent).toMatch(/Not enough money/);

    fireEvent.click(screen.getByLabelText("Close"));
    expect(screen.queryByText("Not enough money")).toBeNull();
});

test("closing one result leaves the others, and with several one button closes them all", () => {
    render(<Page initial={[{ message: "one" }, { message: "two" }, { message: "three" }]} />);
    fireEvent.click(screen.getAllByLabelText("Close")[0]);
    expect(screen.queryByText("one")).toBeNull();
    expect(screen.getByText("two")).toBeTruthy();

    render(<Page initial={[{ message: "a" }, { message: "b" }, { message: "c" }]} />);
    fireEvent.click(screen.getByText("Close all 3"));
    expect(screen.queryByText("a")).toBeNull();
});
