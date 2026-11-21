import React from "react";
import { render } from "@testing-library/react";
import EmpirePolitics from "./empirepolitics";

test("the war and peace rules come from the game config, in hours, never epochs", () => {
    const state = {
        game_config: {
            BASE_EPOCH_SECONDS: 1800,
            AGGRO_PER_ATTACK: 10, AGGRO_PER_AGGRO_SPY: 2, AGGRO_METER_PER_KD: 10, AGGRO_METER_DECAY_PER_KD_PER_EPOCH: 0.25,
            DENOUNCE_DURATION_MULTIPLIER: 48, DENOUNCE_AGGRO_METER_INCREASE: 0.2, DENOUNCE_OFFENSE_BONUS: 0.05,
            WAR_OFFENSE_INCREASE: 0.1, WAR_GAINS_INCREASE: 0.2, WAR_LOSSES_INCREASE: 0.2,
            SURPRISE_WAR_PENALTY_MULTIPLIER: 48, SURPRISE_WAR_PENALTY_OFFENSE_INCREASE: 0.1,
            PEACE_DURATION_MULTIPLIER: 48, PEACE_DEFENSE_BONUS: 0.5, PEACE_PROBE_DEFENSE_BONUS: 0.5,
        },
        surrender_options: { stars: [0, 0.05, 0.1] },
    };
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
    const { container } = render(<EmpirePolitics state={state} />);
    const text = container.textContent.replace(/\s+/g, " ");
    expect(text).toContain("adds 10 to your Empire's aggression");
    expect(text).toContain("falls by 0.5 per hour for each kingdom");
    expect(text).toContain("for 24 hours. It raises your aggression");
    expect(text).toContain("attacks have 10.0% more offense and take 20.0% more");
    expect(text).toContain("For 24 hours afterwards");
    expect(text).toContain("(5.0% or 10.0%, or none)");
    expect(text).toContain("followed by 24 hours of peace");
    expect(text).not.toMatch(/epoch/i);
});
