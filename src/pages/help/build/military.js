import { displayPercent } from "../../../format";
import { inOrder } from "../../../order";
import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Military(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "military") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const unitsDesc = props.state.units || {};
    const prettyNames = props.state.pretty_names || {};
    const unitsRows = inOrder(Object.keys(unitsDesc), props.state.order?.units).map((unitKey, iter) => {
        return <tr key={"units_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[unitKey]}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].cost}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].offense}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].defense}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].hangar_capacity}</td>
            <td style={{textAlign: "right"}}>{unitsDesc[unitKey].fuel}</td>
            <td style={{textAlign: "left"}}>{props.state.projects?.[unitsDesc[unitKey].project]?.name || ""}</td>
            <td style={{textAlign: "left"}}>{prettyNames[unitsDesc[unitKey].upgrades_from] || ""}</td>
        </tr>
    })
    return (
        <div id="military" ref={yourElementRef} className="help-section">
            <h2>Build - Military</h2>
            <p>
                The Recruits page allows you to train recruits. You can train 
                up to {displayPercent(props.state.game_config?.BASE_MAX_RECRUITS_CAP)} of your
                current population at one time.
            </p>
            <p>
                Base recruit cost is {props.state.game_config?.BASE_RECRUIT_COST}. 
                The base average training time is {props.state.game_config?.BASE_EPOCH_SECONDS * (props.state.game_config?.BASE_RECRUIT_TIME_MIN_MULTIPLIER + props.state.game_config?.BASE_RECRUIT_TIME_MAX_MUTLIPLIER) / 2 / 3600} hours.
            </p>
            <p>
                The Specialists page allows you to train recruits into specialists. 
                The base average training time is {props.state.game_config?.BASE_EPOCH_SECONDS * (props.state.game_config?.BASE_SPECIALIST_TIME_MIN_MULTIPLIER + props.state.game_config?.BASE_SPECIALIST_TIME_MAX_MUTLIPLIER) / 2 / 3600} hours.
            </p>
            <p>
                You can exceed your maximum hangar capacity at any time. However, units which do not have a hangar will displace civilians from their homes 
                and cause population loss.
            </p>
            <p>
                The allocate page allows you to specify the target mix of units that you would like the auto-spender to 
                build towards, as well as the maximum number of recruits to train. The auto-spender will first spend funding on training recruits if enabled, 
                and then prioritize training units that are farther from their target allocation. Both 
                currently trained and in-training units are considered when determining the "current" mix of units. The allocation is based on the number of 
                units (i.e. the allocation does not consider cost of the unit). Once your army has exactly the mix you asked for
                (always the case when you ask for a single unit), the auto-spender keeps training in those proportions.
            </p>
            <p>
                Units consume fuel every {props.state.game_config?.BASE_EPOCH_SECONDS} seconds based on the table below.
            </p>
            <p>
                The Disband page allows you to disband units to return them to population and 
                receive {displayPercent(props.state.game_config?.BASE_DISBAND_COST_RETURN)} of the unit's training cost back. 
                This can be useful to get your hangar capacity back to 100% after being attacked multiple times, or to boost your 
                population if you are in danger of dying due to 0 population. Engineers can not be disbanded.
            </p>
            <p>
                Some units can only be trained once a project is completed (the "Unlocked by" column). The heavy and
                elite units pack more strength into each hangar space, so the same hangars hold a stronger army and
                more of your land can go to homes and mines, but each point of their strength costs more money.
            </p>
            <p>
                Each line of units ends in two playstyle units, each unlocked by its own project. They are as strong as
                the best unit of their line and cost more, for a trait: Solar Attackers and Solar Defenders use
                {" "}{displayPercent(props.state.game_config?.SOLAR_FUEL_REDUCTION)} less fuel; Self-Destructing
                Attackers and Defenders raise the other side's losses in battle (see the Attack help); Warp Speed Big
                Flexers all come home with the first general to return; Compact Big Flexers take
                {" "}{props.state.game_config?.COMPACT_FLEX_HANGAR_CAPACITY} hangar space each. A trait belongs to those
                units only, not to the rest of your army.
            </p>
            <p>
                The Upgrade page turns units you already have at home into the next unit of their line (the "Upgrades
                from" column), for the difference between the two units' costs, once the new unit is unlocked. Upgrades go
                one step at a time (Attackers to Heavy Attackers, then Heavy to Elite), never back down, and never from
                one playstyle unit to the other. The units leave at once and come back as the new unit through training,
                taking as long as training does, and do not fight while they upgrade.
            </p>
            <Table className="specialists-table" hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Cost</th>
                        <th style={{textAlign: "right"}}>Offense</th>
                        <th style={{textAlign: "right"}}>Defense</th>
                        <th style={{textAlign: "right"}}>Hangar Usage</th>
                        <th style={{textAlign: "right"}}>Fuel</th>
                        <th style={{textAlign: "left"}}>Unlocked by</th>
                        <th style={{textAlign: "left"}}>Upgrades from</th>
                    </tr>
                </thead>
                <tbody>
                    {unitsRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Military;