import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { authFetch } from "../auth";
import { StrengthForecast } from "./strengthforecast";

jest.mock("../auth", () => ({ authFetch: jest.fn() }));

const state = { game_config: { BASE_EPOCH_SECONDS: 1800, QUEUE_FORECAST_EPOCHS: [2] } };
const later = (hours) => new Date(Date.now() + hours * 3.6e6).toISOString();
const point = (kind, offense, defense, extra = {}) => ({ kind, time: later(kind === "now" ? 0 : 1), offense, defense, generals_home: 2, ...extra });

const answer = (overrides = {}) => ({
    timelines: {
        generals: [point("now", 100, 200), point("general", 150, 260, { general: 0 })],
        production: [point("now", 100, 200), point("horizon", 120, 300, { epochs: 2 })],
        combined: [point("now", 100, 200), point("general", 150, 260), point("horizon", 170, 360, { epochs: 2 })],
    },
    shields: { value: 0.1, known: null, max: 0.1 },
    military_bonus: { value: 0.05, known: 0.05, max: 0.25 },
    fuelless: false, fuel_known: true, production_known: true,
    ...overrides,
});

const respond = (body) => authFetch.mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve(body), headers: { get: () => "application/json" } });

beforeEach(() => {
    jest.useFakeTimers();
    authFetch.mockReset();
});
afterEach(() => jest.useRealTimers());

async function settle() {
    await act(async () => { jest.advanceTimersByTime(600); });
    await act(async () => { await Promise.resolve(); });
}

test("another kingdom's forecast shows the three timelines and where each setting comes from", async () => {
    respond(answer());
    render(<StrengthForecast target="7" state={state} />);
    await settle();

    expect(JSON.parse(authFetch.mock.calls[0][1].body)).toEqual({ target: "7", shields: "", military_bonus: "" });
    expect(screen.getByText("As generals come home")).toBeTruthy();
    expect(screen.getByText("As training lands")).toBeTruthy();
    expect(screen.getByText("Generals and training together")).toBeTruthy();
    expect(screen.getByText("360")).toBeTruthy();
    expect(screen.getByText("Estimate needed")).toBeTruthy();  // shields not revealed: the most there can be
    expect(screen.getByText("Revealed")).toBeTruthy();         // military efficiency revealed
});

test("changing a setting asks the server again with it", async () => {
    respond(answer());
    render(<StrengthForecast target="7" state={state} />);
    await settle();
    fireEvent.change(screen.getByLabelText(/Military shields/), { target: { name: "shields", value: "5" } });
    await settle();

    expect(JSON.parse(authFetch.mock.calls.at(-1)[1].body)).toEqual({ target: "7", shields: "5", military_bonus: "" });
    expect(screen.getByText("Your estimate")).toBeTruthy();
});

test("without production intel there is only the generals timeline, and it says how to get the rest", async () => {
    const { production, combined, ...generalsOnly } = answer().timelines;
    respond(answer({ timelines: generalsOnly, production_known: false }));
    render(<StrengthForecast target="7" state={state} />);
    await settle();

    expect(screen.queryByText("As training lands")).toBeNull();
    expect(screen.getByText(/Spy on production/)).toBeTruthy();
});

test("your own forecast sends no target and tags nothing", async () => {
    respond(answer({ shields: { value: 0.1, known: 0.1, max: 0.1 } }));
    render(<StrengthForecast state={state} />);
    await settle();

    expect(JSON.parse(authFetch.mock.calls[0][1].body)).toEqual({ shields: "", military_bonus: "" });
    expect(screen.queryByText("Revealed")).toBeNull();
    expect(screen.queryByText(/Spy on production/)).toBeNull();
});
