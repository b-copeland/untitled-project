import { displayPercent } from "../../format";
import { inOrder } from "../../order";
import React, { useEffect, useState } from "react";
import {useNavigate} from "react-router-dom";
import {login, authFetch, storeNewTokens, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./status.css";
import HelpButton from "../../components/helpbutton";
import { KingdomLink } from "../../components/kingdomlink";
import Overview from "./overview";

function StatusContent(props) {
    const [key, setKey] = useState('overview');

    return (
    <>
      <Tabs
        id="controlled-tab-example"
        activeKey={key}
        onSelect={(k) => setKey(k)}
        variant="tabs"
      >
        <Tab eventKey="overview" title="Overview">
          <Overview data={props.data} />
        </Tab>
        <Tab eventKey="kingdom" title="Kingdom">
          <Status
            kingdom={props.data.kingdom}
            mobis={props.data.mobis}
            kingdoms={props.data.kingdoms}
            galaxies_inverted={props.data.galaxies_inverted}
            state={props.data.state}
            siphonsout={props.data.siphonsout}
            loading={props.loading}
            updateData={props.updateData}
          />
        </Tab>
        <Tab eventKey="military" title="Military">
          <Military mobis={props.data.mobis} state={props.data.state} />
        </Tab>
        <Tab eventKey="structures" title="Structures">
          <Structures kingdom={props.data.kingdom} structures={props.data.structures} state={props.data.state}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"home"}/>
    </>
    );
}
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.max((Date.parse(date) - Date.now()), 0) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}

function Status(props) {
    const navigate = useNavigate();
    const [clickedReset, setClickedReset] = useState(false);
    if (Object.keys(props.kingdom).length === 0 || Object.keys(props.state).length === 0) {
        return null;
    }
    
    if (clickedReset && !props.loading.kingdomid ) {
        navigate("/createkingdom")
    }
    const onClickReset = (e)=>{
        setClickedReset(true);
        const updateFunc = () => authFetch('api/resetkingdom', {
            method: 'post'
        }).then(storeNewTokens)
        props.updateData(['kingdom', 'kingdomid'], [updateFunc]);
    }

    const unitsFuelCosts = Object.keys(props.kingdom.income?.fuel?.units || {}).sort().map((unit) => 
        <div className="text-box-item" key={unit}>
            <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;{props.state.pretty_names[unit] || unit}</span>
            <span className="text-box-item-value">-{props.kingdom.income?.fuel?.units[unit].toLocaleString()}</span>
        </div>
    )
    const shieldsFuelCosts = Object.keys(props.kingdom.income?.fuel?.shields || {}).sort().map((shield) => 
        <div className="text-box-item" key={shield}>
            <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;{(shield === "spy_radar") ? "Spy radar" : capitalizeFirstLetter(shield) + " shields"}</span>
            <span className="text-box-item-value">-{props.kingdom.income?.fuel?.shields[shield].toLocaleString()}</span>
        </div>
    )
    function getTimeSinceString(date) {
        if (date === undefined) {
            return "--"
        }
        const hours = Math.floor(Math.abs(Date.parse(date) - Date.now()) / 3.6e6);
        const days = Math.floor(hours / 24);
        if (hours > 48) {
            return days.toString() + 'd'
        }
        return hours.toString() + 'h';
    }
    function getLongTimeString(date) {
        if (date === undefined) {
            return "--"
        }
        const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
        if (hours > 24) {
            return getTimeSinceString(date)
        }
        var n = new Date(0, 0);
        n.setSeconds(+hours * 60 * 60);
        return n.toTimeString().slice(0, 8);
    }
    const timeNow = new Date()

    const gameStart = new Date(props.state.state?.game_start);
    const incomeFreqMinutes = (props.state.game_config?.BASE_EPOCH_SECONDS || 0) / 60;

    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.kingdoms[parseInt(kdId)] + " (" + props.galaxies_inverted[kdId] + ")"
        } else {
            return "Unknown"
        }
        
    }

    const siphonsIn = (
        props.kingdom.siphons?.length > 0
        ? props.kingdom.siphons?.map((siphon, iter) =>
            <div className="text-box-item" key={"siphonsin_" + iter}>
                <span className="text-box-item-title">&nbsp;&nbsp;<KingdomLink kdId={siphon.from}>{kdFullLabel(siphon.from)}</KingdomLink></span>
                <span className="text-box-item-value">{Math.floor(siphon.remaining_siphon).toLocaleString()} ({getTimeString(new Date(siphon.time))})</span>
            </div>
        )
        : <div className="text-box-item">
            <span className="text-box-item-title">&nbsp;&nbsp;None</span>
        </div>
    )

    const siphonsOut = (
        props.siphonsout.length > 0
        ? props.siphonsout.map((siphon, iter) =>
            <div className="text-box-item" key={"siphonsout_" + iter}>
                <span className="text-box-item-title">&nbsp;&nbsp;{getTimeString(new Date(siphon.time))}</span>
                <span className="text-box-item-value">{Math.floor(siphon.siphon).toLocaleString()}</span>
            </div>
        )
        : <div className="text-box-item">
            <span className="text-box-item-title">&nbsp;&nbsp;None</span>
        </div>
    )

    return (
        <div className="status">
            {
                timeNow < gameStart
                ? <div className="text-box kingdom-card game-start-card">
                    <span>The game will begin in {getLongTimeString(gameStart)}</span>
                    <br />
                    <span>You can reset your kingdom to its initial state until that time.</span>
                    
                    {props.loading.kingdom
                    ? <Button className="reset-kingdom-button" variant="warning" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="reset-kingdom-button" variant="warning" type="submit" onClick={onClickReset}>
                        Reset Kingdom
                    </Button>
                    }
                </div>
                : null 
            }
            <div className="status-kingdom-content">
                <div className="text-box kingdom-card">
                    <h3>{props.kingdoms[props.kingdom.kdId] || ""} ({props.galaxies_inverted[props.kingdom.kdId] || ""})</h3>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Name</span>
                        <span className="text-box-item-value">{props.kingdoms[props.kingdom.kdId] || ""}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Race</span>
                        <span className="text-box-item-value">{props.kingdom.race}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Networth</span>
                        <span className="text-box-item-value">{props.kingdom.networth?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Stars</span>
                        <span className="text-box-item-value">{props.kingdom.stars?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Population</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.population)?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Fuel</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.fuel)?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Money</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.money)?.toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Engineers</span>
                        <span className="text-box-item-value">{props.kingdom.units?.engineers.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Drones</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.drones)?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Next Spy Attempt</span>
                        <span className="text-box-item-value">{getTimeString(props.kingdom.next_resolve?.spy_attempt)}</span>
                    </div>
                    <br />
                    {unitKeys(props.mobis.units?.current_total, props.state).map((key) => (
                        <div className="text-box-item" key={key}>
                            <span className="text-box-item-title">{props.state.pretty_names?.[key] || key}</span>
                            <span className="text-box-item-value">{(props.mobis.units?.current_total?.[key] || 0).toLocaleString()}</span>
                        </div>
                    ))}
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Planet Busters</span>
                        <span className="text-box-item-value">{props.kingdom.missiles?.planet_busters.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Star Busters</span>
                        <span className="text-box-item-value">{props.kingdom.missiles?.star_busters.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Galaxy Busters</span>
                        <span className="text-box-item-value">{props.kingdom.missiles?.galaxy_busters.toLocaleString()}</span>
                    </div>
                </div>
                <div className="text-box income-box">
                    <h3>Income (per {incomeFreqMinutes} min)</h3>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Money</span>
                        <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.money?.net).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Mines</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.mines).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Population</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.population).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Bonus</span>
                        <span className="text-box-item-value">{displayPercent(props.kingdom.income?.money?.bonus)}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Siphons In</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.income?.money?.siphons_in).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Siphons Out</span>
                        <span className="text-box-item-value">-{Math.floor(props.kingdom.income?.money?.siphons_out).toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Fuel</span>
                        <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.fuel?.net).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Fuel Plants</span>
                        <span className="text-box-item-value">{Math.floor(props.kingdom.income?.fuel?.fuel_plants).toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Bonus</span>
                        <span className="text-box-item-value">{displayPercent(props.kingdom.income?.fuel?.bonus)}</span>
                    </div>
                    <br />
                    {unitsFuelCosts}
                    <br />
                    {shieldsFuelCosts}
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">&nbsp;&nbsp;&nbsp;&nbsp;Population</span>
                        <span className="text-box-item-value">-{Math.floor(props.kingdom.income?.fuel?.population).toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Population</span>
                        <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.population).toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Drones</span>
                        <span className="text-box-item-value" style={{fontWeight: "bold"}}>{Math.floor(props.kingdom.income?.drones).toLocaleString()}</span>
                    </div>
                </div>
                <div className="text-box income-box">
                    <h3>Statuses</h3>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Siphons In</span>
                    </div>
                    {siphonsIn}
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Siphons Out</span>
                    </div>
                    {siphonsOut}
                </div>
            </div>
        </div>
    );
}


function Revealed(props) {
    const revealed_to = props.kingdom?.revealed_to;
    if (revealed_to === undefined) {
        return null
    }
    if (Object.keys(props.kingdoms).length === 0) {
        return null;
    }
    const revealedItems = Object.keys(revealed_to).map((kdId) =>
        <div key={kdId} className="text-box-item">
            <span className="text-box-item-title" >{props.kingdoms[kdId]}</span>
            <span className="text-box-item-value" >{revealed_to[kdId]}</span>
        </div>
    );
    return (
        <div className="revealed">
            <h2>Kingdom Revealed To:</h2>
            <div className="text-box revealed-box">
                {revealedItems}
            </div>

        </div>
    )
}

/**
 * The units to list, in the server's order: recruits and every unit but engineers (shown on their own). A unit that
 * needs a project is only listed once the kingdom has some.
 */
function unitKeys(counts, state) {
    const all = inOrder(Object.keys(state?.units || counts || {}), state?.order?.units).filter((key) => key !== "engineers");
    return all.filter((key) => !state?.units?.[key]?.project || (counts?.[key] || 0) > 0);
}

/** A column heading for a forecast that many epochs ahead, in real time: "30m", "1h", "24h". */
export function horizonLabel(epochs, cfg) {
    const seconds = (epochs || 0) * (cfg?.BASE_EPOCH_SECONDS || 0);
    if (seconds > 0 && seconds < 3600) {
        return `${Math.round(seconds / 60)}m`;
    }
    return `${Math.round((seconds / 3600) * 10) / 10}h`;
}

function ForecastHead({ horizons, cfg }) {
    return (
        <thead>
            <tr>
                <th style={{textAlign: "right"}}></th>
                <th style={{textAlign: "right"}}>Now</th>
                {horizons.map((epochs) => <th key={epochs} style={{textAlign: "right"}}>{horizonLabel(epochs, cfg)}</th>)}
            </tr>
        </thead>
    );
}

const wholeNumber = (value) => Math.floor(value || 0).toLocaleString();

/** One row: the amount now, then now plus what the queue adds by each horizon (``future_<epochs>`` from the API). */
function ForecastRow({ label, now, horizons, at, show = wholeNumber }) {
    return (
        <tr>
            <td style={{textAlign: "left"}}>{label}</td>
            <td style={{textAlign: "right"}}>{show(now || 0)}</td>
            {horizons.map((epochs) => (
                <td key={epochs} style={{textAlign: "right"}}>{show((now || 0) + (at(`future_${epochs}`) || 0))}</td>
            ))}
        </tr>
    );
}

export function Military(props) {
    if (Object.keys(props.mobis).length === 0) {
        return null;
    }
    const units = props.mobis?.units || {};
    const maxOffense = props.mobis?.maxes?.offense || {};
    const maxDefense = props.mobis?.maxes?.defense || {};
    const cfg = props.state?.game_config || {};
    const horizons = cfg.QUEUE_FORECAST_EPOCHS || [];
    return (
        <div className="status-kingdom-content">
            <div className="col-center-card army-info">
                <h2>Armies</h2>
                <Table hover className="army-table" size="sm">
                    <thead>
                        <tr>
                        <th colSpan={2}></th>
                        <th colSpan={4}>Generals</th>
                        </tr>
                    </thead>
                    <thead>
                        <tr>
                            <th style={{textAlign: "left"}}>Unit</th>
                            <th style={{textAlign: "right"}}>Home</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_0?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_1?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_2?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_3?.return_time)}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {unitKeys(units.current_total, props.state).map((key) => (
                            <tr key={key}>
                                <td style={{textAlign: "left"}}>{props.state?.pretty_names?.[key] || key}</td>
                                <td style={{textAlign: "right"}}>{units.current?.[key]?.toLocaleString() || 0}</td>
                                {[0, 1, 2, 3].map((index) => (
                                    <td key={index} style={{textAlign: "right"}}>{units[`general_${index}`]?.[key]?.toLocaleString() || 0}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </Table>
                <Table hover className="army-table" size="sm">
                    <thead>
                        <tr>
                        <th colSpan={2}></th>
                        <th colSpan={4}>Generals</th>
                        </tr>
                    </thead>
                    <thead>
                        <tr>
                            <th style={{textAlign: "right"}}></th>
                            <th style={{textAlign: "right"}}>Home</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_0?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_1?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_2?.return_time)}</th>
                            <th style={{textAlign: "right"}}>{getTimeString(units.general_3?.return_time)}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style={{textAlign: "left"}}>Max offense</td>
                            <td style={{textAlign: "right"}}>{Math.floor(maxOffense.current || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxOffense.current || 0) + (maxOffense.general_0 || 0) + (maxOffense.general_1 || 0) + (maxOffense.general_2 || 0) + (maxOffense.general_3 || 0)).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td style={{textAlign: "left"}}>Max defense</td>
                            <td style={{textAlign: "right"}}>{Math.floor(maxDefense.current || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0)).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor((maxDefense.current || 0) + (maxDefense.general_0 || 0) + (maxDefense.general_1 || 0) + (maxDefense.general_2 || 0) + (maxDefense.general_3 || 0)).toLocaleString()}</td>
                        </tr>
                    </tbody>
                </Table>
            </div>
            <div className="col-center-card mobi-info">
                <h2>Mobilization</h2>
                <div className="table-scroll">
                    <Table hover className="mobis-table" size="sm">
                        <ForecastHead horizons={horizons} cfg={cfg} />
                        <tbody>
                            {unitKeys(units.current_total, props.state).map((key) => (
                                <ForecastRow key={key} label={props.state?.pretty_names?.[key] || key} now={units.current_total?.[key]}
                                    horizons={horizons} at={(name) => units[name]?.[key]} />
                            ))}
                        </tbody>
                    </Table>
                </div>
                <div className="table-scroll">
                    <Table hover className="mobis-table" size="sm">
                        <ForecastHead horizons={horizons} cfg={cfg} />
                        <tbody>
                            <ForecastRow label="Max offense" now={maxOffense.current_total} horizons={horizons} at={(name) => maxOffense[name]} />
                            <ForecastRow label="Max defense" now={maxDefense.current_total} horizons={horizons} at={(name) => maxDefense[name]} />
                        </tbody>
                    </Table>
                </div>
            </div>
        </div>
    )
}

const STRUCTURE_ROWS = [
    ["homes", "Homes"], ["mines", "Mines"], ["fuel_plants", "Fuel Plants"], ["hangars", "Hangars"],
    ["drone_factories", "Drone Factories"], ["missile_silos", "Missile Silos"], ["workshops", "Workshops"],
];

export function Structures(props) {
    if (Object.keys(props.structures || {}).length === 0) {
        return null;
    }
    const cfg = props.state?.game_config || {};
    const horizons = cfg.QUEUE_FORECAST_EPOCHS || [];
    const structures = props.structures;
    const stars = props.kingdom?.stars || 0;
    const share = (count) => (stars ? displayPercent((count || 0) / stars) : "-");
    return (
        <div className="col-center structures-status">
            <h2>Structures</h2>
            <div className="structures-info">
                <div className="table-scroll">
                    <Table hover className="structures-status-table" size="sm">
                        <ForecastHead horizons={horizons} cfg={cfg} />
                        <tbody>
                            {STRUCTURE_ROWS.map(([key, label]) => (
                                <ForecastRow key={key} label={label} now={structures.current?.[key]} horizons={horizons}
                                    at={(name) => structures[name]?.[key]} />
                            ))}
                        </tbody>
                        <ForecastHead horizons={horizons} cfg={cfg} />
                        <tbody>
                            {STRUCTURE_ROWS.map(([key, label]) => (
                                <ForecastRow key={key} label={label} now={structures.current?.[key]} horizons={horizons}
                                    at={(name) => structures[name]?.[key]} show={share} />
                            ))}
                        </tbody>
                    </Table>
                </div>
            </div>
        </div>
    )
}

export default StatusContent;