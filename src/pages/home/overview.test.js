import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { Overview } from "./overview";
import { TourProvider } from "../../components/tour";

// The advice itself is fetched by the Advisors component (advisors.test.js).
jest.mock("./advisors", () => () => <p>advice goes here</p>);

const data = (kingdom = {}) => ({
    kingdom: {
        money: 5000, fuel: 1000, population: 200, stars: 100, generals_available: 2, auto_spending_enabled: true,
        units: { engineers: 7 }, shields: { military: 0.1 }, siphons: [],
        income: { money: { net: 600 }, fuel: { net: -250 }, population: 10 },
        ...kingdom,
    },
    mobis: {
        maxes: { defense: { current: 9999 }, offense: { current: 9999 } },
        now: { defense: 4321, offense: 1234 },  // what the card shows: current, not the best case
        units: { general_0: { return_time: new Date(Date.now() + 2 * 3.6e6).toISOString() } },
        current_hangar_capacity: 50, max_hangar_capacity: 100,
    },
    structures: { current: { homes: 60 }, queued: { homes: 10 } },
    news: [{ time: new Date(Date.now() - 3 * 3.6e6).toISOString(), news: "You were attacked by Delta" }],
    state: { game_config: { BASE_EPOCH_SECONDS: 1800 } },
});
const noSummary = () => new Promise(() => {});  // the summary card stays loading: these tests are about the others
const show = (d) => render(<MemoryRouter><Overview data={d} loadSummary={noSummary} /></MemoryRouter>);

test("the four cards answer the questions a returning player asks", () => {
    show(data());
    ["Economy", "Military", "Growth", "Threats"].forEach((title) => expect(screen.getByText(title)).toBeTruthy());
    expect(screen.getByText("+1,200")).toBeTruthy();          // money per hour
    expect(screen.getByText("-500")).toBeTruthy();            // fuel per hour
    expect(screen.getByText(/runs out in about 2.0 h/)).toBeTruthy();
    expect(screen.getByText("4,321")).toBeTruthy();           // defense at home
    expect(screen.getByText(/1 general out, the next back in 1h 59m|1 general out, the next back in 2h 00m/)).toBeTruthy();
    expect(screen.getByText("30 stars have nothing on them.")).toBeTruthy();
    expect(screen.getByText(/You were attacked by Delta/)).toBeTruthy();
});

test("the economy card links to the Spending tab of Automation", () => {
    show(data());
    expect(screen.getByRole("link", { name: "Economy" }).getAttribute("href")).toBe("/automation?tab=spending");
});

test("an Advisors box comes first, with the advisors' advice in it", () => {
    show(data());
    const titles = screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent);
    expect(titles[0]).toBe("Advisors");
    expect(screen.getByText("advice goes here")).toBeTruthy();
});

test("nothing before the kingdom has loaded", () => {
    const { container } = show({ ...data(), kingdom: {} });
    expect(container.textContent).toBe("");
});

test("the guided tour's reminder is on the overview only after Not now", () => {
    const withTour = (tour) => render(
        <MemoryRouter><TourProvider data={{ preferences: { tour } }} updateData={() => {}}>
            <Overview data={data()} loadSummary={noSummary} />
        </TourProvider></MemoryRouter>
    );
    const { unmount } = withTour("later");
    expect(screen.getByText("Guided tour")).toBeTruthy();
    expect(document.querySelector('[data-tour="status-advisors"]')).toBeTruthy();
    unmount();
    withTour("done");
    expect(screen.queryByText("Guided tour")).toBeNull();
});
