/** 0.256 -> "25.6%" */
export const displayPercent = (fraction) => `${(fraction * 100).toFixed(1)}%`;

/** Like displayPercent, but nothing at all (rather than "NaN%") when there is no value yet. */
export const displayPercentOrNothing = (fraction) => (fraction != null ? displayPercent(fraction) : null);

/** 1234567.8 -> "1,234,568". Missing or non-numeric values count as 0. */
export const displayNumber = (value) => Math.floor(Number(value) || 0).toLocaleString();

/**
 * A whole number in at most five characters, for a label that must keep its width: exact below 10,000 ("9,999"),
 * then rounded down to thousands, millions or billions ("33k", "1.2m", "33m", "4.5b"). Rounded down, so it never
 * shows more than there is.
 */
export const displayShort = (value) => {
    const number = Number(value);
    const n = Number.isFinite(number) ? Math.max(Math.floor(number), 0) : 0;
    if (n < 10000) return n.toLocaleString();
    const units = [[1e9, "b"], [1e6, "m"], [1e3, "k"]];
    for (const [size, letter] of units) {
        if (n >= size) {
            const scaled = n / size;
            const shown = scaled < 10 ? Math.floor(scaled * 10) / 10 : Math.floor(scaled);
            return `${shown >= 1000 ? Math.floor(shown).toLocaleString() : shown}${letter}`;
        }
    }
    return n.toLocaleString();
};
