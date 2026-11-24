import React from "react";
import { inOrder } from "../../../order";
import { HelpTable, Topic, averageDuration, config, num, pct, perHour } from "../util";

function Military(props) {
    const cfg = config(props.state);
    const units = props.state.units || {};
    const names = props.state.pretty_names || {};
    const rows = inOrder(Object.keys(units), props.state.order?.units).map((key) => {
        const unit = units[key];
        // Recruits and engineers are priced in the config, not in the units table.
        const cost = unit.cost ?? { recruits: cfg.BASE_RECRUIT_COST, engineers: cfg.BASE_ENGINEER_COST }[key];
        return [
            names[key] || key, num(cost), num(unit.offense), num(unit.defense), num(unit.hangar_capacity),
            num(perHour(unit.fuel, cfg)), props.state.projects?.[unit.project]?.name || "", names[unit.upgrades_from] || "",
        ];
    });
    return (
        <Topic id="military" title="Military" lead="Train recruits, turn them into units, and keep your army the right shape.">
            <h4>Recruits</h4>
            <p>
                Every unit starts as a recruit. Recruits cost {num(cfg.BASE_RECRUIT_COST)} each and take
                {" "}{averageDuration(cfg.BASE_RECRUIT_TIME_MIN_MULTIPLIER, cfg.BASE_RECRUIT_TIME_MAX_MUTLIPLIER, cfg)} on
                average. You can train up to {pct(cfg.BASE_MAX_RECRUITS_CAP)} of your population at once.
            </p>
            <h4>The units table</h4>
            <p>The switch above the table changes what it does:</p>
            <ul>
                <li><b>Train</b>: turn recruits into units, in {averageDuration(cfg.BASE_SPECIALIST_TIME_MIN_MULTIPLIER, cfg.BASE_SPECIALIST_TIME_MAX_MUTLIPLIER, cfg)} on average.</li>
                <li><b>Upgrade</b>: turn units at home into the next unit of their line, for the difference in cost. One step at a time (Attackers to Heavy, Heavy to Elite), never back down, and never from one playstyle unit to the other. The units leave at once, take as long as training, and do not fight meanwhile.</li>
                <li><b>Allocate</b>: the mix of units auto spending trains, by number of units, not cost. It trains whatever is furthest below its share, counting units in training. Once the mix is met it keeps training in the same proportions. The switch sets whether it trains recruits first. Max Recruits stops it drafting more once you have that many recruits, counting those in training. Recruits take the longest to arrive, so the quick-start plans train them first with no maximum: your population is the limit, and their homes are sized for the recruits their spending can turn into units.</li>
                <li><b>Disband</b>: turn units (or recruits) back into population for {pct(cfg.BASE_DISBAND_COST_RETURN)} of their cost. Use it to get back under your hangar space, or to save a kingdom about to run out of population. Engineers can not be disbanded.</li>
            </ul>
            <h4>Hangars</h4>
            <p>
                Each unit takes hangar space (the table's Hangar column). You can train past your hangar space, but
                each space over it lowers the population your homes can hold by one, so your population falls.
            </p>
            <h4>Unlocked units</h4>
            <p>
                Heavy and elite units fit more strength into each hangar space, so the same hangars hold a stronger army,
                but each point of strength costs more. Each line ends in two playstyle units, each unlocked by its own
                project. They match the best unit of their line, cost more, and have a trait that applies to them alone:
            </p>
            <ul>
                <li><b>Solar</b> Attackers and Defenders use {pct(cfg.SOLAR_FUEL_REDUCTION)} less fuel.</li>
                <li><b>Self-Destructing</b> Attackers and Defenders raise the other side's losses in battle (see Attack).</li>
                <li><b>Warp Speed</b> Big Flexers all come home with the first general to return.</li>
                <li><b>Compact</b> Big Flexers take {num(cfg.COMPACT_FLEX_HANGAR_CAPACITY)} hangar space each.</li>
            </ul>
            <HelpTable
                columns={[["Unit"], ["Cost", "right"], ["Offense", "right"], ["Defense", "right"], ["Hangar", "right"],
                    ["Fuel / h", "right"], ["Unlocked by"], ["Upgrades from"]]}
                rows={rows} />
        </Topic>
    );
}

export default Military;
