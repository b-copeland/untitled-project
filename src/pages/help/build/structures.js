import React from "react";
import { HelpTable, Topic, averageDuration, config, duration, num, pct, perHour } from "../util";

function Structures(props) {
    const cfg = config(props.state);
    const names = props.state.pretty_names || {};
    const effects = {
        homes: `Houses ${num(cfg.BASE_HOMES_CAPACITY)} population`,
        mines: `Makes ${num(perHour(cfg.BASE_MINES_INCOME_PER_EPOCH, cfg))} money per hour`,
        fuel_plants: `Makes ${num(perHour(cfg.BASE_FUEL_PLANTS_INCOME_PER_EPOCH, cfg))} fuel per hour and stores ${num(cfg.BASE_FUEL_PLANTS_CAPACITY)} fuel`,
        hangars: `Holds ${num(cfg.BASE_HANGAR_CAPACITY)} units`,
        drone_factories: `Makes ${num(perHour(cfg.BASE_DRONE_FACTORIES_PRODUCTION_PER_EPOCH, cfg))} drones per hour`,
        missile_silos: `Holds ${num(cfg.BASE_MISSILE_SILO_CAPACITY)} of each kind of missile`,
        workshops: `Houses ${num(cfg.BASE_WORKSHOP_CAPACITY)} engineers`,
    };
    return (
        <Topic id="structures" title="Structures" lead="One structure per star. Structures are your economy.">
            <ul>
                <li><b>Build</b>: order structures. Each one takes {averageDuration(cfg.BASE_STRUCTURE_TIME_MIN_MULTIPLIER, cfg.BASE_STRUCTURE_TIME_MAX_MUTLIPLIER, cfg)} on average and costs stars<sup>{num(cfg.BASE_STRUCTURE_STARS_POWER)}</sup> × {num(cfg.BASE_STRUCTURE_COST_CONSTANT)}, so they get dearer as you grow.</li>
                <li><b>Allocate</b>: the mix auto spending builds towards. It builds whichever structure is furthest below its share, counting those still being built.</li>
                <li><b>Raze</b>: destroy structures to free their stars, for {pct(cfg.BASE_STRUCTURES_RAZE_RETURN)} of today's build cost back.</li>
            </ul>
            <p>
                If you have more structures than stars, for example after losing an attack, the extra ones fall apart.
                Every {duration(1, cfg)} you lose {pct(cfg.BASE_STRUCTURES_LOSS_RETURN_RATE)} of the extra structures,
                or as many structures as {pct(cfg.BASE_STRUCTURES_LOSS_PER_STAR_PER_EPOCH)} of your stars, whichever is more.
            </p>
            <p>
                The numbers below are before bonuses. Projects raise them: Pop Bonus for homes, Fuel Bonus for fuel
                plants, and a one-time project for each of the others.
            </p>
            <HelpTable columns={[["Structure"], ["What it does"]]}
                rows={Object.keys(effects).map((key) => [names[key] || key, effects[key]])} />
        </Topic>
    );
}

export default Structures;
