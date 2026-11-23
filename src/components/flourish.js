import React, { useEffect, useState } from "react";
import "./flourish.css";

/**
 * Short animations over the page when an action lands: an attack won or lost, a spy operation passed or failed,
 * missiles striking (some shot down by shields) and an election result revealed. They are flair only: the result
 * toast still says what happened, they never block the page (a tap or a key skips one), and they do not play when the
 * player turned Effects off in Settings or the device asks to reduce motion.
 *
 * App.js mounts one `FlourishLayer`; a page calls `playFlourish` (or `flourishResult` with the server's answer).
 * Each scene is a pure function of the time since it started, so it can be checked at any moment.
 */

const listeners = new Set();

/** Plays an effect: `{ kind: "attack" | "spy" | "missiles" | "election", outcome: "success" | "failure", ... }`. */
export function playFlourish(effect) {
    listeners.forEach((listener) => listener(effect));
}

/**
 * Plays the effect for an action's answer from the server, if the action went ahead: an attack or spy operation that
 * succeeded or failed, or missiles that struck. A refused request (no status, or "error") plays nothing.
 */
export function flourishResult(kind, result) {
    if (!result || (result.status !== "success" && result.status !== "failure")) {
        return;
    }
    playFlourish({ kind, outcome: result.status, shieldsStopped: result.shields_stopped || 0 });
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

// The stage is 320 by 160, with the target planet on the right.
const PLANET = { x: 262, y: 80, r: 28 };
const STARS = [[18, 22], [60, 132], [96, 40], [140, 150], [170, 18], [208, 140], [230, 30], [300, 150], [310, 20],
    [40, 76], [120, 96], [196, 64]];

function Backdrop() {
    return (
        <g className="fl-backdrop">
            {STARS.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.2 : 0.7} className="fl-star" />)}
        </g>
    );
}

function Planet({ flash = 0, tone = "accent" }) {
    return (
        <g className="fl-planet">
            <circle cx={PLANET.x} cy={PLANET.y} r={PLANET.r} className="fl-planet-body" />
            <ellipse cx={PLANET.x} cy={PLANET.y} rx={PLANET.r + 14} ry={7} className="fl-planet-ring"
                transform={`rotate(-14 ${PLANET.x} ${PLANET.y})`} />
            {flash > 0 ? (
                <circle cx={PLANET.x} cy={PLANET.y} r={PLANET.r + 4 + 10 * (1 - flash)} className={`fl-glow fl-${tone}`}
                    style={{ opacity: flash }} />
            ) : null}
        </g>
    );
}

function Ship({ x, y, angle = 0 }) {
    return (
        <g transform={`translate(${x} ${y}) rotate(${angle})`} className="fl-ship">
            <path d="M-13,-3 L-19,0 L-13,3 Z" className="fl-engine" />
            <path d="M8,0 L-12,-7 L-8,0 L-12,7 Z" className="fl-hull" />
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
                const rad = (a * Math.PI) / 180;
                const inner = 6 + 10 * p;
                const outer = 9 + 16 * p;
                return <line key={a} x1={Math.cos(rad) * inner} y1={Math.sin(rad) * inner}
                    x2={Math.cos(rad) * outer} y2={Math.sin(rad) * outer} className={`fl-spark fl-${tone}`} />;
            })}
        </g>
    );
}

function Beam({ from, to, show }) {
    return show ? <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} className="fl-beam" /> : null;
}

// ---- Attack ---------------------------------------------------------------------------------------------------------

const ATTACK_SHIPS = [52, 66, 80, 94, 108];
const ATTACK_LOST_ON_WIN = [3];

/** Where attacking ship `i` is at `t`, and whether it is still flying. */
export function attackShip(i, t, won) {
    const delay = i * 0.1;
    const y0 = ATTACK_SHIPS[i];
    const approach = easeOut(span(t, delay, delay + 1.0));
    const stopX = 196 + (i % 2) * 8;
    const lost = !won || ATTACK_LOST_ON_WIN.includes(i);
    const dies = lost ? delay + 0.85 + (won ? 0 : i * 0.12) : Infinity;
    const x = lerp(-24, stopX, approach);
    if (t >= dies) {
        return { x: lerp(-24, stopX, easeOut(span(dies, delay, delay + 1.0))), y: y0, alive: false, dies };
    }
    if (t < delay + 1.0) {
        return { x, y: y0, angle: 0, alive: true, dies };
    }
    // Past the planet and away, up and to the right.
    const leave = easeIn(span(t, delay + 1.0, delay + 2.0));
    const lx = lerp(stopX, 380, leave);
    const ly = lerp(y0, y0 - 70, leave * leave);
    return { x: lx, y: ly, angle: -25 * leave, alive: true, dies };
}

function AttackScene({ t, won }) {
    const ships = ATTACK_SHIPS.map((_, i) => attackShip(i, t, won));
    const flash = won ? span(t, 1.2, 1.5) * (1 - span(t, 1.9, 2.4)) : 0;
    return (
        <>
            <Planet flash={flash} tone="success" />
            {ships.map((ship, i) => (
                <g key={i}>
                    {ship.alive ? <Ship x={ship.x} y={ship.y} angle={ship.angle} /> : null}
                    {ship.alive && ship.dies === Infinity ? null : (
                        <>
                            <Beam from={PLANET} to={ship} show={t > ship.dies - 0.14 && t < ship.dies} />
                            <Burst x={ship.x} y={ship.y} p={span(t, ship.dies, ship.dies + 0.5)} />
                        </>
                    )}
                </g>
            ))}
            {won ? [0.75, 0.9, 1.05].map((at, k) => (
                <Burst key={k} x={PLANET.x - 20 + k * 9} y={PLANET.y - 10 + k * 9} p={span(t, at, at + 0.4)} size={0.6}
                    tone="warning" />
            )) : null}
        </>
    );
}

// ---- Spy ------------------------------------------------------------------------------------------------------------

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
    const arrive = easeOut(span(t, 0, 0.7));
    let x = lerp(-16, 214, arrive);
    let y = lerp(122, 72, arrive) + Math.sin(t * 9) * 2;
    if (passed && t > 1.15) {
        const leave = easeIn(span(t, 1.15, 1.7));
        x = lerp(214, 360, leave);
        y = lerp(72 + Math.sin(1.15 * 9) * 2, 20, leave);
    }
    return { x, y, alive: passed || t < 0.95 };
}

function Mark({ passed, p }) {
    if (p <= 0) {
        return null;
    }
    const length = 40;
    const d = passed ? "M-8,0 L-2,7 L10,-8" : "M-7,-7 L7,7 M7,-7 L-7,7";
    return (
        <g transform={`translate(${PLANET.x} ${PLANET.y - PLANET.r - 18})`}>
            <circle r={13} className={`fl-mark-ring fl-${passed ? "success" : "danger"}`} style={{ opacity: p }} />
            <path d={d} className={`fl-mark fl-${passed ? "success" : "danger"}`}
                style={{ strokeDasharray: length, strokeDashoffset: length * (1 - p) }} />
        </g>
    );
}

function SpyScene({ t, passed }) {
    const drone = spyDrone(t, passed);
    const scan = passed ? span(t, 0.7, 0.85) * (1 - span(t, 1.05, 1.2)) : 0;
    return (
        <>
            <Planet flash={passed ? span(t, 0.7, 0.8) * (1 - span(t, 1.0, 1.3)) : 0} tone="success" />
            {scan > 0 ? (
                <polygon points={`${drone.x},${drone.y} ${PLANET.x - PLANET.r * 0.7},${PLANET.y - PLANET.r * 0.7} ${PLANET.x - PLANET.r * 0.7},${PLANET.y + PLANET.r * 0.7}`}
                    className="fl-scan" style={{ opacity: scan * 0.35 }} />
            ) : null}
            {drone.alive ? <Drone x={drone.x} y={drone.y} /> : null}
            {passed ? null : (
                <>
                    <Beam from={PLANET} to={drone} show={t > 0.8 && t < 0.95} />
                    <Burst x={drone.x} y={drone.y} p={span(t, 0.95, 1.4)} size={0.8} />
                </>
            )}
            <Mark passed={passed} p={span(t, 0.9, 1.25)} />
        </>
    );
}

// ---- Missiles -------------------------------------------------------------------------------------------------------

const MISSILES = 6;
const SHIELD_R = 44;
const LAUNCH = { x: 30, y: 152 };
const PEAK = { x: 140, y: -40 };
const missileAt = (s) => ({
    x: (1 - s) * (1 - s) * LAUNCH.x + 2 * (1 - s) * s * PEAK.x + s * s * PLANET.x,
    y: (1 - s) * (1 - s) * LAUNCH.y + 2 * (1 - s) * s * PEAK.y + s * s * PLANET.y,
});
const distance = (point) => Math.hypot(point.x - PLANET.x, point.y - PLANET.y);
/** How far along the arc (0 to 1) a missile first comes within `radius` of the planet's centre. */
const reach = (radius) => {
    let s = 0;
    while (s < 1 && distance(missileAt(s)) > radius) s += 0.002;
    return s;
};
const SHIELD_AT = reach(SHIELD_R);
const SURFACE_AT = reach(PLANET.r);

/**
 * How many of the animation's missiles the shields shoot down, for the share of the damage they stopped: at least one
 * when they stopped any, and at least one gets through unless they stopped all of it.
 */
export function shotDownCount(share, missiles = MISSILES) {
    if (!(share > 0)) return 0;
    if (share >= 1) return missiles;
    return clamp(Math.round(share * missiles), 1, missiles - 1);
}

/** Which missiles are shot down: spread through the salvo rather than the first few. */
export function shotDownMissiles(count, missiles = MISSILES) {
    return Array.from({ length: missiles }, (_, i) => Math.floor(((i + 1) * count) / missiles) > Math.floor((i * count) / missiles));
}

const MISSILE_FLIGHT = 1.2;

function MissilesScene({ t, shieldsStopped }) {
    const count = shotDownCount(shieldsStopped);
    const downs = shotDownMissiles(count);
    const shield = count > 0 ? span(t, 0.3, 0.6) * (1 - span(t, 2.2, 2.6)) : 0;
    const hits = [];
    const parts = downs.map((down, i) => {
        const start = i * 0.13;
        const end = down ? SHIELD_AT : SURFACE_AT;
        const s = span(t, start, start + MISSILE_FLIGHT) ;
        const at = easeInOut(s);
        const ends = start + MISSILE_FLIGHT * inverseEaseInOut(end);
        if (!down) hits.push(ends);
        if (t < ends) {
            const head = missileAt(at);
            const tail = missileAt(Math.max(at - 0.06, 0));
            return t >= start ? (
                <g key={i}>
                    <line x1={tail.x} y1={tail.y} x2={head.x} y2={head.y} className="fl-trail" />
                    <circle cx={head.x} cy={head.y} r={2.2} className="fl-missile" />
                </g>
            ) : null;
        }
        const point = missileAt(end);
        return <Burst key={i} x={point.x} y={point.y} p={span(t, ends, ends + 0.45)} size={down ? 0.6 : 0.8}
            tone={down ? "accent" : "danger"} />;
    });
    const flash = hits.length ? Math.max(...hits.map((at) => span(t, at, at + 0.1) * (1 - span(t, at + 0.2, at + 0.6)))) : 0;
    return (
        <>
            <Planet flash={flash} tone="danger" />
            {shield > 0 ? <circle cx={PLANET.x} cy={PLANET.y} r={SHIELD_R} className="fl-shield" style={{ opacity: shield }} /> : null}
            {parts}
        </>
    );
}

/** The time fraction at which easeInOut reaches `value`. */
function inverseEaseInOut(value) {
    return value < 0.5 ? Math.sqrt(value / 2) : 1 - Math.sqrt((1 - value) / 2);
}

// ---- Election -------------------------------------------------------------------------------------------------------

function ElectionScene({ t, lines }) {
    const open = easeInOut(span(t, 0.5, 1.6));
    return (
        <div className="fl-election">
            <div className="fl-election-reveal" style={{ opacity: span(t, 0.9, 1.5) }}>
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
        seconds: 2.7,
        caption: (effect) => (effect.outcome === "success" ? "Attack won" : "Attack failed"),
        draw: (t, effect) => <AttackScene t={t} won={effect.outcome === "success"} />,
    },
    spy: {
        seconds: 1.9,
        caption: (effect) => (effect.outcome === "success" ? "Operation succeeded" : "Operation failed"),
        draw: (t, effect) => <SpyScene t={t} passed={effect.outcome === "success"} />,
    },
    missiles: {
        seconds: 2.9,
        caption: (effect) => {
            const count = shotDownCount(effect.shieldsStopped);
            return count === 0 ? "Missiles struck" : count === MISSILES ? "Shields stopped them all" : "Shields stopped some";
        },
        tone: (effect) => (shotDownCount(effect.shieldsStopped) === MISSILES ? "failure" : "success"),
        draw: (t, effect) => <MissilesScene t={t} shieldsStopped={effect.shieldsStopped} />,
    },
    election: { seconds: 5, html: true, draw: (t, effect) => <ElectionScene t={t} lines={effect.lines} /> },
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
    const fade = span(t, 0, 0.15) * (1 - span(t, scene.seconds - 0.35, scene.seconds));
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
                <div className={`fl-caption fl-caption-${tone}`} style={{ opacity: span(t, 0.9, 1.2) }}>{caption}</div>
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
 * plays at a time; a new one replaces it. Hidden from screen readers, since the result toast says the same in words.
 */
export function FlourishLayer({ enabled }) {
    const [effect, setEffect] = useState(null);
    useEffect(() => {
        if (!enabled) {
            setEffect(null);
            return undefined;
        }
        const listener = (next) => {
            if (SCENES[next.kind] && !reducedMotion()) {
                setEffect({ ...next, startedAt: performance.now() });
            }
        };
        listeners.add(listener);
        return () => listeners.delete(listener);
    }, [enabled]);
    if (!effect) {
        return null;
    }
    return (
        <div className="flourish-layer" aria-hidden="true" data-testid="flourish">
            <Playing key={effect.startedAt} effect={effect} onDone={() => setEffect(null)} />
        </div>
    );
}
