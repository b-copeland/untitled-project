import React from "react";
import { render, screen } from "@testing-library/react";
import Spy from "./spy";

test("the siphon description gives the payout and the cap from the game config", () => {
    const state = {
        game_config: {
            BASE_DRONES_SIPHON_PER_DRONE: 8, BASE_DRONES_SIPHON_TIME_MULTIPLIER: 12,
            BASE_EPOCH_SECONDS: 1800, BASE_MAX_SIPHON: 0.15,
        },
        pretty_names: { siphonfunds: "Siphon Funds" },
    };
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
    render(<Spy state={state} />);
    const text = screen.getByText(/money per drone, paid evenly/).textContent;
    expect(text).toContain("8 money per drone, paid evenly over the next 6 hours");
    expect(text).toContain("15.0%");
    expect(text).toContain("the oldest siphon is reduced first");
    expect(text).toContain("If the siphoning kingdom dies, its siphons end.");
    expect(text).not.toContain("proportional");
});
