import { checkChoices, kingdomStats } from "./kingdomstats";

const state = {
    units: { attack: { offense: 5, fuel: 1, hangar_capacity: 1 }, defense: { defense: 4, fuel: 1, hangar_capacity: 1 } },
    structures: { pop_per_home: 10, income_per_mine: 3, hangar_capacity: 100, engineers_capacity_per_workshop: 50 },
    income_per_pop: 2,
    fuel_consumption_per_pop: 0.5,
};

test("stats follow from the units and structures, whether numbers or typed text", () => {
    const stats = kingdomStats(state, { attack: 10, defense: "5", engineers: 20 }, { homes: "6", mines: 4, hangars: 1, workshops: 1 });
    expect(stats).toMatchObject({
        offense: 50, defense: 20, population: 60, income: 60 * 2 + 4 * 3, fuelUsage: 15 + 60 * 0.5,
        hangarUsed: 15, hangarCapacity: 100, engineers: 20, workshopCapacity: 50,
    });
});

test("empty boxes and unknown units count as nothing", () => {
    expect(kingdomStats(state, { attack: "", cannons: 5 }, {})).toMatchObject({ offense: 0, population: 0, income: 0 });
});

describe("checkChoices", () => {
    const rules = { selection_points: { drones: 1, attack: 5 }, total_points: 100, total_stars: 10 };
    const choose = (units, structures, race = "Xo") => checkChoices({ units, structures, race }, rules);

    test("is happy when every point and star is spent and a race is chosen", () => {
        expect(choose({ drones: 50, attack: 10 }, { homes: 10 })).toEqual({ pointsLeft: 0, starsLeft: 0, blocked: null });
    });

    test("says what is wrong, points first", () => {
        expect(choose({ drones: 40, attack: 10 }, { homes: 9 }).blocked).toBe("Spend all 100 unit points (10 left)");
        expect(choose({ drones: 60, attack: 10 }, { homes: 10 }).blocked).toBe("10 unit points over");
        expect(choose({ drones: 50, attack: 10 }, { homes: 9 }).blocked).toBe("Place all 10 stars (1 left)");
        expect(choose({ drones: 50, attack: 10 }, { homes: 11 }).blocked).toBe("1 stars over");
        expect(choose({ drones: 50, attack: 10 }, { homes: 10 }, "").blocked).toBe("Choose a race");
    });

    test("reads text typed into the boxes", () => {
        expect(choose({ drones: "50", attack: "10" }, { homes: "4", mines: "6" }).blocked).toBeNull();
    });
});
