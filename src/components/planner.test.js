import React from "react";
import { render, screen, act } from "@testing-library/react";
import { useServerForecast } from "./planner";

function Probe({ plan, ask }) {
    const [answer, pending] = useServerForecast(plan, ask, 700);
    return <div>{pending ? "pending" : "settled"}:{answer.value ?? "none"}</div>;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

test("a burst of changes is one request, sent after the pause, and the same plan is not asked twice", async () => {
    const ask = jest.fn((plan) => Promise.resolve({ value: plan.n }));
    const { rerender } = render(<Probe plan={null} ask={ask} />);
    rerender(<Probe plan={{ n: 1 }} ask={ask} />);
    for (let n = 2; n <= 30; n++) {          // a slider being dragged
        rerender(<Probe plan={{ n }} ask={ask} />);
        act(() => { jest.advanceTimersByTime(20); });
    }
    expect(ask).not.toHaveBeenCalled();
    expect(screen.getByText(/pending/)).toBeTruthy();

    await act(async () => { jest.advanceTimersByTime(800); });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(ask).toHaveBeenCalledWith({ n: 30 });
    expect(screen.getByText("settled:30")).toBeTruthy();

    rerender(<Probe plan={{ n: 30 }} ask={ask} />);
    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(ask).toHaveBeenCalledTimes(1);
});

test("nothing is asked while there is no plan", async () => {
    const ask = jest.fn(() => Promise.resolve({}));
    render(<Probe plan={null} ask={ask} />);
    await act(async () => { jest.advanceTimersByTime(2000); });
    expect(ask).not.toHaveBeenCalled();
});
