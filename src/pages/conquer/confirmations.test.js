import { attackNeedsConfirmation } from "./attack";
import { spyNeedsConfirmation } from "./spy";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

test("a winning attack on a revealed army is sent without asking", () => {
    expect(attackNeedsConfirmation({ unitsKnown: true, hasForecast: true, wins: true })).toBe(false);
});

test("an attack asks first when their army is not revealed, when there is no forecast, or when it would fail", () => {
    expect(attackNeedsConfirmation({ unitsKnown: false, hasForecast: true, wins: true })).toBe(true);
    expect(attackNeedsConfirmation({ unitsKnown: true, hasForecast: false, wins: false })).toBe(true);
    expect(attackNeedsConfirmation({ unitsKnown: true, hasForecast: true, wins: false })).toBe(true);
});

test("an intel operation with a fair chance is sent without asking", () => {
    expect(spyNeedsConfirmation({ group: "Gather intel", hasForecast: true, guessing: false, chance: 0.7 })).toBe(false);
    expect(spyNeedsConfirmation({ group: "Gather intel", hasForecast: false, guessing: true, chance: 0 })).toBe(false);
});

test("hostile operations are sent without asking too", () => {
    expect(spyNeedsConfirmation({ group: "Hostile", hasForecast: true, guessing: false, chance: 0.9 })).toBe(false);
});

test("only a known long shot asks first", () => {
    expect(spyNeedsConfirmation({ hasForecast: true, guessing: false, chance: 0.2 })).toBe(true);
    // A chance that is only a guess is not a reason to ask.
    expect(spyNeedsConfirmation({ hasForecast: true, guessing: true, chance: 0.2 })).toBe(false);
});
