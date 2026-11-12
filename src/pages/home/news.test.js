import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { NewsFeed, timeAgo } from "./news";

const now = Date.parse("2026-01-02T12:00:00Z");

test("times are given as how long ago", () => {
    expect(timeAgo("2026-01-02T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-01-02T11:30:00Z", now)).toBe("30m ago");
    expect(timeAgo("2026-01-02T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2025-12-29T12:00:00Z", now)).toBe("4d ago");
});

const items = [
    { time: "2026-01-01T00:00:00Z", from: "1", to: "", news: "Old news" },
    { time: "2026-01-02T00:00:00Z", from: "", to: "", news: "Newer news" },
];

test("newest first, and the search narrows the list", () => {
    render(<NewsFeed items={items} name={(id) => "Kd" + id} />);
    const texts = screen.getAllByText(/news/i).map((node) => node.textContent).filter((text) => /Old|Newer/.test(text));
    expect(texts).toEqual(["Newer news", "Old news"]);
    fireEvent.change(screen.getByLabelText("Search the news"), { target: { value: "kd1" } });
    expect(screen.queryByText("Newer news")).toBeNull();
    expect(screen.getByText("Old news")).toBeTruthy();
});

test("says so when there is nothing", () => {
    render(<NewsFeed items={[]} name={() => ""} empty="No news." />);
    expect(screen.getByText("No news.")).toBeTruthy();
});
