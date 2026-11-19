import { inOrder, entriesInOrder } from "./order";

test("keys come back in the game's order, unknown keys last", () => {
    expect(inOrder(["big_flex", "attack", "zzz", "defense"], ["attack", "defense", "big_flex"]))
        .toEqual(["attack", "defense", "big_flex", "zzz"]);
});

test("without an order the keys stay as they came", () => {
    expect(inOrder(["b", "a"], undefined)).toEqual(["b", "a"]);
    expect(entriesInOrder({ b: 1, a: 2 }, ["a", "b"])).toEqual([["a", 2], ["b", 1]]);
});
