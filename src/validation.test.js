import { anyFilled, checkCount, checkPercent, checkTotal, firstError } from "./validation";

describe("checkCount", () => {
    test("empty means none and is fine", () => {
        expect(checkCount("")).toBeNull();
        expect(checkCount(undefined)).toBeNull();
        expect(checkCount("  ")).toBeNull();
    });
    test("whole numbers are fine, anything else is not", () => {
        expect(checkCount("12")).toBeNull();
        expect(checkCount("0")).toBeNull();
        ["-3", "1.5", "abc", "1e3", "1,000"].forEach((bad) => expect(checkCount(bad)).toMatch(/whole number/));
    });
    test("over the maximum says what the maximum is", () => {
        expect(checkCount("5", { max: 5 })).toBeNull();
        expect(checkCount("6", { max: 5 })).toBe("At most 5");
        expect(checkCount("2000", { max: 1500.7, noun: "structures" })).toBe("At most 1,500 structures");
    });
});

describe("checkPercent", () => {
    test("decimals up to 100 are fine", () => {
        expect(checkPercent("12.5")).toBeNull();
        expect(checkPercent("100")).toBeNull();
        expect(checkPercent("")).toBeNull();
    });
    test("negative, text and over 100 are not", () => {
        expect(checkPercent("-1")).toMatch(/percentage/);
        expect(checkPercent("ten")).toMatch(/percentage/);
        expect(checkPercent("100.1")).toBe("At most 100%");
        expect(checkPercent("60", { max: 50 })).toBe("At most 50%");
    });
});

describe("checkTotal", () => {
    test("adds the fields up, ignoring empty ones", () => {
        expect(checkTotal({ a: "40", b: "", c: "60" }, { max: 100 })).toBeNull();
        expect(checkTotal({ a: "40", b: "61" }, { max: 100 })).toBe("Total 101 is over the limit of 100");
        expect(checkTotal({ a: "3", b: "4" }, { max: 5, noun: "structures" })).toBe("Total 7 is over the limit of 5 structures");
    });
});

test("anyFilled needs a non-zero value somewhere", () => {
    expect(anyFilled({ a: "", b: "" })).toBe(false);
    expect(anyFilled({ a: "0", b: " " })).toBe(false);
    expect(anyFilled({ a: "", b: "3" })).toBe(true);
});

test("firstError finds the first message among values, objects and nulls", () => {
    expect(firstError(null, { a: null, b: "bad" }, "later")).toBe("bad");
    expect(firstError({ a: null }, null)).toBeNull();
    expect(firstError("only")).toBe("only");
});
