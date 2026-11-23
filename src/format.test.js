import { displayShort } from "./format";

test("displayShort is exact below 10,000 and short above, rounded down, in at most five characters", () => {
    const cases = [
        [0, "0"], [7, "7"], [9999, "9,999"], [10000, "10k"], [33123, "33k"], [999999, "999k"],
        [1000000, "1m"], [1290000, "1.2m"], [33333333, "33m"], [999999999, "999m"],
        [4567000000, "4.5b"], [1.5e13, "15,000b"], [-5, "0"], [undefined, "0"], [Infinity, "0"],
    ];
    for (const [value, shown] of cases) expect(displayShort(value)).toBe(shown);
    for (let n = 1; n < 1e12; n *= 7) expect(displayShort(n).length).toBeLessThanOrEqual(5);
});
