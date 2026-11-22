import React from "react";
import { render, screen } from "@testing-library/react";
import { Empire } from "./news";

jest.mock("../../components/helpbutton", () => () => null);

test("the empire tab lists each line of empire news", () => {
    const time = new Date(Date.now() - 2 * 3.6e6).toISOString();
    render(<Empire empirenews={[
        { time, news: "One declared a surprise war on Two" },
        { time, news: "Galaxy 1:2 joined the empire" },
    ]} />);
    expect(screen.getByText("One declared a surprise war on Two")).toBeTruthy();
    expect(screen.getByText("Galaxy 1:2 joined the empire")).toBeTruthy();
    expect(screen.queryByText("To")).toBeNull();
});

test("an empty empire tab says what will show there", () => {
    render(<Empire empirenews={[]} />);
    expect(screen.getByText(/No empire news yet/)).toBeTruthy();
});
