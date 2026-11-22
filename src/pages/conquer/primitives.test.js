import React from "react";
import { render, screen } from "@testing-library/react";
import { RobPrimitives } from "./primitives";

jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({}) })) }));

const data = (modifiers) => ({
    kingdom: { drones: 1000, spy_attempts: 3 },
    state: { primitives_rob_per_drone: 4, game_config: {} },
    modifiers,
});

test("the rob forecast is the kingdom's own figure once it has loaded", () => {
    render(<RobPrimitives data={data({ primitives_rob_per_drone: 4.8 })} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText(/about 4\.80 money per drone/)).toBeTruthy();
});

test("until then it is the universe's", () => {
    render(<RobPrimitives data={data({})} loading={{}} updateData={jest.fn()} />);
    expect(screen.getByText(/about 4\.00 money per drone/)).toBeTruthy();
});
