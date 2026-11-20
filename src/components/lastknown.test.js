import React from "react";
import { render, screen } from "@testing-library/react";
import { withLastKnown, staleness, ago, Known, LastKnownNote } from "./lastknown";

const HOUR = 3.6e6;
const config = { BASE_EPOCH_SECONDS: 3600, LAST_KNOWN_FRESH_EPOCHS: 12, LAST_KNOWN_AGING_EPOCHS: 24 };
const hoursAgo = (hours) => new Date(Date.now() - hours * HOUR).toISOString();

test("live values win over snapshots, down to each nested value", () => {
    const military = hoursAgo(5);
    const kingdomEnded = hoursAgo(30);
    const { kingdom, endedOf, categories } = withLastKnown({
        name: "Delta",
        stars: 400,  // stats are live
        units: { engineers: 12 },  // projects intel is live: the engineers only
        last_known: {
            military: { ended: military, values: { units: { attack: 100, engineers: 3 }, generals_out: [] } },
            kingdom: { ended: kingdomEnded, values: { stars: 350, money: 999 } },
        },
    });
    expect(kingdom).toMatchObject({ name: "Delta", stars: 400, money: 999, units: { attack: 100, engineers: 12 }, generals_out: [] });
    expect(kingdom.last_known).toBeUndefined();
    expect(endedOf("stars")).toBeUndefined();
    expect(endedOf("units.engineers")).toBeUndefined();
    expect(endedOf("units.attack")).toBe(military);
    expect(endedOf("money")).toBe(kingdomEnded);
    expect(endedOf("units")).toBe(military);  // a nested object: the earliest of what came from snapshots
    expect(endedOf("generals_out")).toBe(military);
    expect(categories).toEqual({ military, kingdom: kingdomEnded });
});

test("a newer snapshot wins over an older one where both have a value", () => {
    const older = hoursAgo(20);
    const newer = hoursAgo(2);
    const { kingdom, endedOf } = withLastKnown({ last_known: {
        stats: { ended: newer, values: { stars: 500 } },
        kingdom: { ended: older, values: { stars: 300, fuel: 10 } },
    } });
    expect(kingdom.stars).toBe(500);
    expect(endedOf("stars")).toBe(newer);
    expect(endedOf("fuel")).toBe(older);
});

test("nothing to lay under: the kingdom as sent", () => {
    expect(withLastKnown({ name: "A", stars: 1 }).kingdom).toEqual({ name: "A", stars: 1 });
    expect(withLastKnown(undefined).kingdom).toEqual({});
});

test("staleness is yellow under 12 hours, orange under 24, red after", () => {
    expect(staleness(hoursAgo(1), config)).toBe("fresh");
    expect(staleness(hoursAgo(11.9), config)).toBe("fresh");
    expect(staleness(hoursAgo(12.1), config)).toBe("aging");
    expect(staleness(hoursAgo(23.9), config)).toBe("aging");
    expect(staleness(hoursAgo(24.1), config)).toBe("stale");
    // The thresholds are epochs: with a half-hour epoch, 7 hours is already orange.
    expect(staleness(hoursAgo(7), { ...config, BASE_EPOCH_SECONDS: 1800 })).toBe("aging");
});

test("ages are in real time", () => {
    const now = Date.now();
    expect(ago(new Date(now - 40 * 60000).toISOString(), now)).toBe("40m ago");
    expect(ago(new Date(now - 5 * HOUR).toISOString(), now)).toBe("5h ago");
    expect(ago(new Date(now - 51 * HOUR).toISOString(), now)).toBe("2d 3h ago");
});

test("a snapshot value is coloured and says how old it is; a live one is plain", () => {
    render(<>
        <Known ended={hoursAgo(30)} gameConfig={config}>1,234</Known>
        <Known gameConfig={config}>5,678</Known>
        <LastKnownNote ended={hoursAgo(13)} gameConfig={config} />
    </>);
    const old = screen.getByText("1,234");
    expect(old.className).toContain("last-known-stale");
    expect(old.getAttribute("title")).toBe("Last known, 30h ago");
    expect(screen.getByText("5,678").className || "").not.toContain("last-known");
    expect(screen.getByText(/are last known, from intel that ended 13h ago/).className).toContain("last-known-aging");
});
