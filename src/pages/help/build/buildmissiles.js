import React from "react";
import { HelpTable, Topic, config, num } from "../util";

function BuildMissiles(props) {
    const cfg = config(props.state);
    const names = props.state.pretty_names || {};
    const missiles = props.state.missiles || {};
    return (
        <Topic id="buildmissiles" title="Build Missiles" lead="Missiles damage a kingdom without risking your army.">
            <p>
                Each missile silo holds {num(cfg.BASE_MISSILE_SILO_CAPACITY)} of each kind of missile, counting those
                still being built. Missiles cost money and fuel. Launch them from the Launch Missiles page.
            </p>
            <HelpTable
                columns={[["Missile"], ["Cost", "right"], ["Fuel cost", "right"], ["Stars destroyed", "right"], ["Fuel destroyed", "right"], ["Population killed", "right"]]}
                rows={Object.keys(missiles).map((key) => [
                    names[key] || key, num(missiles[key].cost), num(missiles[key].fuel_cost),
                    num(missiles[key].stars_damage), num(missiles[key].fuel_damage), num(missiles[key].pop_damage),
                ])} />
        </Topic>
    );
}

export default BuildMissiles;
