import { attackUnits, defenderUnits } from "./attack";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

const unitsDesc = {
    attack: { offense: 5, defense: 0 },
    elite_attack: { offense: 7, defense: 0, project: "elite_attackers" },
    defense: { offense: 0, defense: 5 },
    elite_defense: { offense: 0, defense: 7, project: "elite_defenders" },
    flex: { offense: 5, defense: 5 },
    recruits: { offense: 0, defense: 1 },
    engineers: { offense: 0, defense: 0 },
};

test("the units you can send are every unit with offense, in the server's order", () => {
    expect(attackUnits(unitsDesc, { elite_attack: "Elite Attackers" })).toEqual([
        ["attack", "attack"], ["elite_attack", "Elite Attackers"], ["flex", "flex"],
    ]);
});

test("the units that defend are every unit with defense, recruits included", () => {
    expect(defenderUnits(unitsDesc).map(([key]) => key)).toEqual(["elite_defense", "defense", "flex", "recruits"].sort((a, b) =>
        Object.keys(unitsDesc).indexOf(a) - Object.keys(unitsDesc).indexOf(b)));
});
