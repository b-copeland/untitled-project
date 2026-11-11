/** 0.256 -> "25.6%" */
export const displayPercent = (fraction) => `${(fraction * 100).toFixed(1)}%`;

/** Like displayPercent, but nothing at all (rather than "NaN%") when there is no value yet. */
export const displayPercentOrNothing = (fraction) => (fraction != null ? displayPercent(fraction) : null);

/** 1234567.8 -> "1,234,568". Missing or non-numeric values count as 0. */
export const displayNumber = (value) => Math.floor(Number(value) || 0).toLocaleString();
