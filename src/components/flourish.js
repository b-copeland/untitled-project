import React, { useEffect, useRef, useState } from "react";
import "./flourish.css";

/**
 * Short animations over the page when an action lands: an attack won or lost, a spy operation passed or failed,
 * missiles striking (some shot down by shields) and an election result revealed. Attacks and spy operations open the
 * same way whatever happened, hold for a moment, and only then show the outcome.
 *
 * They are flair only: they never block the page (a tap or a key skips one), and they do not play when the player
 * turned Effects off in Settings or the device asks to reduce motion. A page waits for one to finish before showing
 * its result toast, so the toast does not give the ending away.
 *
 * App.js mounts one `FlourishLayer`; a page calls `flourishResult` with the server's answer (or `playFlourish`), and
 * the promise it returns settles when the effect has finished, at once if none plays. Each scene is a pure
 * function of the time since it started, so it can be checked at any moment.
 */

const listeners = new Set();

/**
 * Plays an effect: `{ kind: "attack" | "spy" | "missiles" | "election", outcome: "success" | "failure", ... }`.
 * Returns a promise that settles when it has finished or was skipped, or at once if it does not play.
 */
export function playFlourish(effect) {
    return new Promise((resolve) => {
        let taken = false;
        listeners.forEach((listener) => {
            if (listener(effect, resolve)) taken = true;
        });
        if (!taken) resolve();
    });
}

/**
 * Plays the effect for an action's answer from the server, if the action went ahead: an attack or spy operation that
 * succeeded or failed, or missiles that struck. A refused request (no status, or "error") plays nothing. Returns a
 * promise that settles when the effect is over, for the page to show its toast then.
 */
export function flourishResult(kind, result) {
    if (!result || (result.status !== "success" && result.status !== "failure")) {
        return Promise.resolve();
    }
    return playFlourish({ kind, outcome: result.status, shieldsStopped: result.shields_stopped || 0 });
}

const reducedMotion = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// ---- Geometry -------------------------------------------------------------------------------------------------------

const clamp = (value, low = 0, high = 1) => Math.min(Math.max(value, low), high);
const lerp = (a, b, p) => a + (b - a) * p;
/** How far along `t` is between `start` and `end`, from 0 to 1. */
const span = (t, start, end) => clamp((t - start) / (end - start));
const easeOut = (p) => 1 - (1 - p) * (1 - p);
const easeIn = (p) => p * p;
const easeInOut = (p) => (p < 0.5 ? 2 * p * p : 1 - 2 * (1 - p) * (1 - p));
/** The time fraction at which easeInOut reaches `value`. */
const inverseEaseInOut = (value) => (value < 0.5 ? Math.sqrt(value / 2) : 1 - Math.sqrt((1 - value) / 2));
const radians = (degrees) => (degrees * Math.PI) / 180;

// The stage is 320 by 160.
const STARS = [[18, 22], [60, 132], [96, 40], [140, 150], [170, 18], [208, 140], [230, 30], [300, 150], [310, 20],
    [40, 76], [120, 96], [196, 64]];

function Backdrop() {
    return (
        <g className="fl-backdrop">
            {STARS.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.2 : 0.7} className="fl-star" />)}
        </g>
    );
}

function Planet({ x, y, r, flash = 0, tone = "accent", ring = true }) {
    return (
        <g className="fl-planet">
            <circle cx={x} cy={y} r={r} className="fl-planet-body" />
            {ring ? <ellipse cx={x} cy={y} rx={r + 14} ry={7} className="fl-planet-ring" transform={`rotate(-14 ${x} ${y})`} /> : null}
            {flash > 0 ? (
                <circle cx={x} cy={y} r={r + 4 + 10 * (1 - flash)} className={`fl-glow fl-${tone}`} style={{ opacity: flash }} />
            ) : null}
        </g>
    );
}

function Ship({ x, y, angle = 0, enemy = false }) {
    return (
        <g transform={`translate(${x} ${y}) rotate(${angle})`} className="fl-ship">
            <path d="M-13,-3 L-19,0 L-13,3 Z" className="fl-engine" />
            <path d="M8,0 L-12,-7 L-8,0 L-12,7 Z" className={enemy ? "fl-hull-enemy" : "fl-hull"} />
        </g>
    );
}

/** An explosion `p` of the way through (0 to 1). */
function Burst({ x, y, p, size = 1, tone = "danger" }) {
    if (!(p > 0 && p < 1)) {
        return null;
    }
    const sparks = [0, 60, 120, 180, 240, 300];
    return (
        <g transform={`translate(${x} ${y}) scale(${size})`} style={{ opacity: 1 - easeIn(p) }}>
            <circle r={3 + 13 * easeOut(p)} className={`fl-burst fl-${tone}`} />
            <circle r={2 + 6 * easeOut(p)} className="fl-burst-core" />
            {sparks.map((a) => {
                const inner = 6 + 10 * p;
                const outer = 9 + 16 * p;
                return <line key={a} x1={Math.cos(radians(a)) * inner} y1={Math.sin(radians(a)) * inner}
                    x2={Math.cos(radians(a)) * outer} y2={Math.sin(radians(a)) * outer} className={`fl-spark fl-${tone}`} />;
            })}
        </g>
    );
}

function Beam({ from, to, show, tone = "danger" }) {
    return show ? <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} className={`fl-beam fl-${tone}`} /> : null;
}

/** A tick or a cross in a ring at (`x`, `y`), drawn `p` of the way. */
function Mark({ x, y, passed, p }) {
    if (p <= 0) {
        return null;
    }
    const length = 40;
    const d = passed ? "M-8,0 L-2,7 L10,-8" : "M-7,-7 L7,7 M7,-7 L-7,7";
    return (
        <g transform={`translate(${x} ${y})`}>
            <circle r={13} className={`fl-mark-ring fl-${passed ? "success" : "danger"}`} style={{ opacity: p }} />
            <path d={d} className={`fl-mark fl-${passed ? "success" : "danger"}`}
                style={{ strokeDasharray: length, strokeDashoffset: length * (1 - p) }} />
        </g>
    );
}

// ---- Attack: two fleets ---------------------------------------------------------------------------------------------

// Arrive, trade fire (the same either way), hold, then the reveal and, after a win, the fleet flies on.
export const ATTACK = { arrive: 1.2, fireFrom: 1.25, fireTo: 2.4, reveal: 3.0, leave: 4.1, seconds: 5.4 };
const FLEET_Y = { ours: [44, 62, 80, 98, 116], theirs: [47, 65, 83, 101, 119] };
// The opening exchange: shots back and forth that hit nothing.
const OPENING_SHOTS = Array.from({ length: 9 }, (_, k) => ({
    at: ATTACK.fireFrom + k * 0.13, side: k % 2 === 0 ? "ours" : "theirs", from: (k * 3) % 5, to: (k * 2 + 1) % 5,
}));
// When each ship that is lost blows up, by side and index.
const LOSSES = {
    won: { ours: { 3: 3.3 }, theirs: { 2: 3.05, 0: 3.3, 4: 3.5, 1: 3.7, 3: 3.9 } },
    lost: { ours: { 2: 3.05, 0: 3.25, 4: 3.45, 1: 3.65, 3: 3.85 }, theirs: { 1: 3.2 } },
};
const other = (side) => (side === "ours" ? "theirs" : "ours");

function fleetPlace(side, i, t, won) {
    const ours = side === "ours";
    const arrive = easeOut(span(t, i * 0.08, i * 0.08 + ATTACK.arrive));
    const holdX = ours ? 92 - (i % 2) * 12 : 228 + (i % 2) * 12;
    let x = lerp(ours ? -24 : 344, holdX, arrive);
    let y = FLEET_Y[side][i] + Math.sin(t * 3 + i) * 1.5;
    let angle = ours ? 0 : 180;
    if (ours && won && t > ATTACK.leave) {
        const leave = easeIn(span(t, ATTACK.leave, ATTACK.leave + 0.9));
        x = lerp(holdX, 380, leave);
        y -= 30 * leave;
        angle = -12 * leave;
    }
    return { x, y, angle };
}

/** Where ship `i` of `side` ("ours" or "theirs") is at `t`, whether it is still flying, and when it is lost. */
export function fleetShip(side, i, t, won) {
    const dies = LOSSES[won ? "won" : "lost"][side][i] ?? Infinity;
    const place = fleetPlace(side, i, Math.min(t, dies), won);
    return { ...place, alive: t < dies, dies };
}

/** The ship on the other side that fires the shot that destroys ship `i` of `side`: one still flying then. */
function shooter(side, i, at, won) {
    for (let k = 0; k < 5; k++) {
        const j = (i + 2 + k) % 5;
        if (fleetShip(other(side), j, at, won).alive) return j;
    }
    return i;
}

function AttackScene({ t, won }) {
    const ships = ["ours", "theirs"].flatMap((side) => [0, 1, 2, 3, 4].map((i) => ({ side, i, ...fleetShip(side, i, t, won) })));
    const at = (side, i) => ships.find((ship) => ship.side === side && ship.i === i);
    return (
        <>
            <Planet x={352} y={80} r={52} ring={false} />
            {OPENING_SHOTS.map((shot, k) => {
                const from = at(shot.side, shot.from);
                const to = at(other(shot.side), shot.to);
                return (
                    <g key={k}>
                        <Beam from={from} to={to} show={t > shot.at && t < shot.at + 0.1} tone={shot.side === "ours" ? "warning" : "danger"} />
                        <Burst x={to.x} y={to.y} p={span(t, shot.at + 0.08, shot.at + 0.35)} size={0.3} tone="warning" />
                    </g>
                );
            })}
            {ships.map((ship) => (
                <g key={`${ship.side}${ship.i}`}>
                    {ship.alive ? <Ship x={ship.x} y={ship.y} angle={ship.angle} enemy={ship.side === "theirs"} /> : null}
                    {ship.dies === Infinity ? null : (
                        <>
                            <Beam from={at(other(ship.side), shooter(ship.side, ship.i, ship.dies, won))} to={ship}
                                show={t > ship.dies - 0.14 && t < ship.dies} tone={ship.side === "ours" ? "danger" : "warning"} />
                            <Burst x={ship.x} y={ship.y} p={span(t, ship.dies, ship.dies + 0.55)} />
                        </>
                    )}
                </g>
            ))}
        </>
    );
}

// ---- Spy ------------------------------------------------------------------------------------------------------------

// The drone flies in and scans while the planet's searchlight sweeps; a pause; then it is spotted or slips away.
export const SPY = { arrive: 1.2, scanTo: 2.3, reveal: 2.7, seconds: 4.3 };
const SPY_PLANET = { x: 268, y: 80, r: 30 };
const DRONE_AT = { x: 196, y: 80 };

function Drone({ x, y }) {
    return (
        <g transform={`translate(${x} ${y})`} className="fl-drone">
            <line x1={-9} y1={0} x2={9} y2={0} className="fl-drone-arm" />
            <circle r={5} className="fl-hull" />
            <circle r={1.8} className="fl-drone-eye" />
        </g>
    );
}

export function spyDrone(t, passed) {
    const arrive = easeOut(span(t, 0, SPY.arrive));
    let x = lerp(-16, DRONE_AT.x, arrive);
    let y = lerp(124, DRONE_AT.y, arrive) + Math.sin(t * 4) * 2;
    if (passed && t > 3.0) {
        const leave = easeIn(span(t, 3.0, 3.8));
        x = lerp(DRONE_AT.x, 360, leave);
        y = lerp(DRONE_AT.y + Math.sin(3.0 * 4) * 2, 18, leave);
    }
    return { x, y, alive: passed || t < 2.95 };
}

/** The searchlight's direction in degrees (180 points straight at the drone): the same sweep until the reveal, then
 * it locks on to the drone, or swings away. */
export function searchlight(t, passed) {
    const sweep = (time) => 180 + 50 * Math.sin((time - 0.6) * 2.4);
    if (t <= SPY.reveal) return sweep(t);
    return lerp(sweep(SPY.reveal), passed ? 100 : 180, easeOut(span(t, SPY.reveal, SPY.reveal + 0.2)));
}

function SpyScene({ t, passed }) {
    const drone = spyDrone(t, passed);
    const scanning = t > SPY.arrive + 0.1 && t < SPY.scanTo ? 0.25 + 0.15 * Math.sin(t * 14) : 0;
    const angle = searchlight(t, passed);
    const light = span(t, 1.0, 1.4) * (1 - (passed ? span(t, 3.4, 3.8) : 0));
    const edge = { x: SPY_PLANET.x + Math.cos(radians(angle)) * SPY_PLANET.r, y: SPY_PLANET.y + Math.sin(radians(angle)) * SPY_PLANET.r };
    const reach = 130;
    const cone = [angle - 9, angle + 9].map((a) => `${SPY_PLANET.x + Math.cos(radians(a)) * reach},${SPY_PLANET.y + Math.sin(radians(a)) * reach}`);
    return (
        <>
            {light > 0 ? <polygon points={`${edge.x},${edge.y} ${cone.join(" ")}`} className="fl-searchlight" style={{ opacity: 0.28 * light }} /> : null}
            <Planet {...SPY_PLANET} flash={passed ? span(t, 2.75, 2.85) * (1 - span(t, 3.0, 3.4)) : 0} tone="success" />
            {scanning > 0 ? (
                <polygon points={`${drone.x},${drone.y} ${SPY_PLANET.x - SPY_PLANET.r * 0.7},${SPY_PLANET.y - SPY_PLANET.r * 0.7} ${SPY_PLANET.x - SPY_PLANET.r * 0.7},${SPY_PLANET.y + SPY_PLANET.r * 0.7}`}
                    className="fl-scan" style={{ opacity: scanning }} />
            ) : null}
            {drone.alive ? <Drone x={drone.x} y={drone.y} /> : null}
            {passed ? null : (
                <>
                    <Beam from={edge} to={drone} show={t > 2.85 && t < 2.95} />
                    <Burst x={drone.x} y={drone.y} p={span(t, 2.95, 3.5)} size={0.8} />
                </>
            )}
            <Mark x={SPY_PLANET.x} y={SPY_PLANET.y - SPY_PLANET.r - 18} passed={passed} p={span(t, 3.0, 3.4)} />
        </>
    );
}

// ---- Missiles -------------------------------------------------------------------------------------------------------

const MISSILES = 6;
const MISSILE_PLANET = { x: 258, y: 84, r: 22 };
const SHIELD_R = 60;
const LAUNCH = { x: 24, y: 152 };
const PEAK = { x: 120, y: -50 };
const MISSILE_FLIGHT = 1.9;
const missileStart = (i) => 0.4 + i * 0.32;
const missileAt = (s) => ({
    x: (1 - s) * (1 - s) * LAUNCH.x + 2 * (1 - s) * s * PEAK.x + s * s * MISSILE_PLANET.x,
    y: (1 - s) * (1 - s) * LAUNCH.y + 2 * (1 - s) * s * PEAK.y + s * s * MISSILE_PLANET.y,
});
const distance = (point) => Math.hypot(point.x - MISSILE_PLANET.x, point.y - MISSILE_PLANET.y);
/** How far along the arc (0 to 1) a missile first comes within `radius` of the planet's centre. */
const reach = (radius) => {
    let s = 0;
    while (s < 1 && distance(missileAt(s)) > radius) s += 0.002;
    return s;
};
const SHIELD_AT = reach(SHIELD_R);
const SURFACE_AT = reach(MISSILE_PLANET.r);

/**
 * How many of the animation's missiles the shields shoot down, for the share of the damage they stopped: at least one
 * when they stopped any, and at least one gets through unless they stopped all of it.
 */
export function shotDownCount(share, missiles = MISSILES) {
    if (!(share > 0)) return 0;
    if (share >= 1) return missiles;
    return clamp(Math.round(share * missiles), 1, missiles - 1);
}

/** Which missiles are shot down: always the last ones, so the salvo hits first and the shields hold at the end. */
export function shotDownMissiles(count, missiles = MISSILES) {
    return Array.from({ length: missiles }, (_, i) => i >= missiles - count);
}

/** When missile `i` ends: at the shield if it is shot down, at the surface if not. */
const missileEnds = (i, down) => missileStart(i) + MISSILE_FLIGHT * inverseEaseInOut(down ? SHIELD_AT : SURFACE_AT);

function MissilesScene({ t, shieldsStopped }) {
    const count = shotDownCount(shieldsStopped);
    const downs = shotDownMissiles(count);
    const ends = downs.map((down, i) => missileEnds(i, down));
    const flashOf = (times) => (times.length ? Math.max(...times.map((at) => span(t, at, at + 0.08) * (1 - span(t, at + 0.15, at + 0.6)))) : 0);
    const shieldFlash = flashOf(ends.filter((_, i) => downs[i]));
    const shield = count > 0 ? span(t, 0.2, 0.6) * (1 - span(t, 4.5, 4.9)) : 0;
    return (
        <>
            <Planet {...MISSILE_PLANET} flash={flashOf(ends.filter((_, i) => !downs[i]))} tone="danger" />
            {shield > 0 ? (
                <circle cx={MISSILE_PLANET.x} cy={MISSILE_PLANET.y} r={SHIELD_R} className="fl-shield"
                    style={{ opacity: shield, strokeWidth: 1.5 + 2.5 * shieldFlash }} />
            ) : null}
            {downs.map((down, i) => {
                const start = missileStart(i);
                if (t < start) return null;
                if (t < ends[i]) {
                    const at = easeInOut(span(t, start, start + MISSILE_FLIGHT));
                    const head = missileAt(at);
                    const tail = missileAt(Math.max(at - 0.06, 0));
                    return (
                        <g key={i}>
                            <line x1={tail.x} y1={tail.y} x2={head.x} y2={head.y} className="fl-trail" />
                            <circle cx={head.x} cy={head.y} r={2.4} className="fl-missile" />
                        </g>
                    );
                }
                const point = missileAt(down ? SHIELD_AT : SURFACE_AT);
                return <Burst key={i} x={point.x} y={point.y} p={span(t, ends[i], ends[i] + 0.5)} size={down ? 0.6 : 0.9}
                    tone={down ? "accent" : "danger"} />;
            })}
        </>
    );
}

// ---- Election -------------------------------------------------------------------------------------------------------

function ElectionScene({ t, lines }) {
    const open = easeInOut(span(t, 1.2, 3.2));
    return (
        <div className="fl-election">
            <div className="fl-election-reveal" style={{ opacity: span(t, 2.0, 3.0) }}>
                <div className="fl-election-title">The universe has voted</div>
                {(lines || []).map((line) => <div key={line} className="fl-election-line">{line}</div>)}
            </div>
            <div className="fl-curtain fl-curtain-left" style={{ transform: `translateX(${-100 * open}%)` }} />
            <div className="fl-curtain fl-curtain-right" style={{ transform: `translateX(${100 * open}%)` }} />
            <div className="fl-valance" />
        </div>
    );
}

// ---- The layer ------------------------------------------------------------------------------------------------------

const SCENES = {
    attack: {
        seconds: ATTACK.seconds,
        captionAt: 3.6,
        caption: (effect) => (effect.outcome === "success" ? "Attack won" : "Attack failed"),
        draw: (t, effect) => <AttackScene t={t} won={effect.outcome === "success"} />,
    },
    spy: {
        seconds: SPY.seconds,
        captionAt: 3.0,
        caption: (effect) => (effect.outcome === "success" ? "Operation succeeded" : "Operation failed"),
        draw: (t, effect) => <SpyScene t={t} passed={effect.outcome === "success"} />,
    },
    missiles: {
        seconds: 5.0,
        captionAt: 3.9,
        caption: (effect) => {
            const count = shotDownCount(effect.shieldsStopped);
            return count === 0 ? "Missiles struck" : count === MISSILES ? "Shields stopped them all" : "Shields stopped some";
        },
        tone: (effect) => (shotDownCount(effect.shieldsStopped) === MISSILES ? "failure" : "success"),
        draw: (t, effect) => <MissilesScene t={t} shieldsStopped={effect.shieldsStopped} />,
    },
    election: { seconds: 8, html: true, draw: (t, effect) => <ElectionScene t={t} lines={effect.lines} /> },
};

/** Seconds since `startedAt`, redrawn every frame until `seconds` have passed. */
function useClock(startedAt, seconds) {
    const [now, setNow] = useState(startedAt);
    useEffect(() => {
        if (!window.requestAnimationFrame) {
            return undefined;
        }
        let frame;
        const tick = () => {
            const time = performance.now();
            setNow(time);
            if (time - startedAt < seconds * 1000) frame = window.requestAnimationFrame(tick);
        };
        frame = window.requestAnimationFrame(tick);
        return () => window.cancelAnimationFrame(frame);
    }, [startedAt, seconds]);
    return Math.max((now - startedAt) / 1000, 0);
}

/** One effect playing: the scene, faded in at the start and out at the end, with its caption. */
export function FlourishStage({ effect, t }) {
    const scene = SCENES[effect.kind];
    const fade = span(t, 0, 0.2) * (1 - span(t, scene.seconds - 0.4, scene.seconds));
    const tone = scene.tone ? scene.tone(effect) : effect.outcome;
    const caption = scene.caption?.(effect);
    return (
        <div className={`fl-stage fl-stage-${effect.kind}`} style={{ opacity: fade }}>
            {scene.html ? scene.draw(t, effect) : (
                <svg viewBox="0 0 320 160" className="fl-svg" role="presentation">
                    <Backdrop />
                    {scene.draw(t, effect)}
                </svg>
            )}
            {caption ? (
                <div className={`fl-caption fl-caption-${tone}`} style={{ opacity: span(t, scene.captionAt, scene.captionAt + 0.3) }}>
                    {caption}
                </div>
            ) : null}
        </div>
    );
}

function Playing({ effect, onDone }) {
    const scene = SCENES[effect.kind];
    const t = useClock(effect.startedAt, scene.seconds);
    useEffect(() => {
        const timer = setTimeout(onDone, scene.seconds * 1000);
        // Any tap, click or key skips it; the tap still does whatever it was for.
        const skip = () => onDone();
        window.addEventListener("pointerdown", skip);
        window.addEventListener("keydown", skip);
        return () => {
            clearTimeout(timer);
            window.removeEventListener("pointerdown", skip);
            window.removeEventListener("keydown", skip);
        };
    }, [effect]); // eslint-disable-line react-hooks/exhaustive-deps
    return <FlourishStage effect={effect} t={t} />;
}

/**
 * Where the effects play: one, in App.js, over every page. `enabled` is the player's Effects setting. Only one effect
 * plays at a time; a new one replaces it (and the old one's promise settles). Hidden from screen readers, since the
 * result toast says the same in words.
 */
export function FlourishLayer({ enabled }) {
    const [effect, setEffect] = useState(null);
    const playing = useRef(null);
    const finish = () => {
        playing.current?.resolve();
        playing.current = null;
        setEffect(null);
    };
    useEffect(() => {
        if (!enabled) {
            return undefined;
        }
        const listener = (next, resolve = () => {}) => {
            if (!SCENES[next.kind] || reducedMotion()) {
                return false;
            }
            playing.current?.resolve();
            playing.current = { ...next, resolve, startedAt: performance.now() };
            setEffect(playing.current);
            return true;
        };
        listeners.add(listener);
        return () => {
            listeners.delete(listener);
            finish();
        };
    }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps
    if (!effect) {
        return null;
    }
    return (
        <div className="flourish-layer" aria-hidden="true" data-testid="flourish">
            <Playing key={effect.startedAt} effect={effect} onDone={finish} />
        </div>
    );
}
