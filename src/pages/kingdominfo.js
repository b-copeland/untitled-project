import { displayPercentOrNothing as displayPercent } from "../format";
import { inOrder, entriesInOrder } from "../order";
import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./kingdominfo.css";
import HelpButton from "../components/helpbutton";
import { Known, LastKnownNote } from "../components/lastknown";


/**
 * Another kingdom's details, as far as they are revealed. ``intelActions(category, inline)`` (optional, from
 * conquer/intel.js) gives what you can do about each kind of intel on it: shown at the top of the tab that kind of intel
 * fills, and next to the single value it reveals (drones).
 *
 * Values from last-known intel (``data.endedOf`` and ``data.lastKnown``, from components/lastknown.js) are coloured by
 * how old they are, and a tab whose intel has ended says so at its top.
 */
function KingdomContent(props) {
    const [key, setKey] = useState('kingdom');
    const actions = props.intelActions || (() => null);
    const gameConfig = props.data.state?.game_config;
    const endedOf = props.data.endedOf || (() => undefined);
    const known = { endedOf, gameConfig };
    const note = (category) => <LastKnownNote ended={props.data.lastKnown?.[category]} gameConfig={gameConfig} />;

    return (
        <>
        <Tabs
            id="controlled-tab-example"
            defaultActiveKey="kingdom"
            variant="tabs"
        >
            <Tab eventKey="kingdom" title="Kingdom">
            {actions("kingdom")}
            {note("kingdom")}
            <Kingdom kingdom={props.data.kingdom} state={props.data.state} kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} kdId={props.data.kdId} actions={actions} known={known}/>
            </Tab>
            <Tab eventKey="military" title="Military">
            {actions("military")}
            {note("military")}
            <Military kingdom={props.data.kingdom} state={props.data.state} known={known} />
            </Tab>
            <Tab eventKey="structures" title="Structures">
            {actions("structures")}
            {note("structures")}
            <Structures kingdom={props.data.kingdom} known={known}/>
            </Tab>
            <Tab eventKey="projects" title="Projects">
            {actions("projects")}
            {note("projects")}
            <Projects kingdom={props.data.kingdom} state={props.data.state} known={known}/>
            </Tab>
            <Tab eventKey="shields" title="Shields">
            {actions("shields")}
            {note("shields")}
            <Shields kingdom={props.data.kingdom} shields={props.data.shields} known={known}/>
            </Tab>
        </Tabs>
        <HelpButton scrollTarget={"viewkingdom"}/>
        </>
    );
}

/** ``value`` as shown for the field at ``path``: coloured when it comes from last-known intel. */
const shown = (known, path, value) => <Known ended={known?.endedOf(path)} gameConfig={known?.gameConfig}>{value}</Known>;

/** One label and value; a value not known shows a muted "?". */
function Fact({ label, children }) {
    const blank = children === undefined || children === null || children === "";
    return (
        <div className="text-box-item">
            <span className="text-box-item-title">{label}</span>
            <span className="text-box-item-value">{blank ? <span className="kd-unknown" title="Not revealed">?</span> : children}</span>
        </div>
    );
}

/** A titled card of facts. */
function FactCard({ title, children }) {
    return (
        <div className="text-box kingdom-card kd-card">
            <h3>{title}</h3>
            {children}
        </div>
    );
}

function Kingdom(props) {
    const kd = props.kingdom || {};
    const has = (value) => value !== undefined && value !== null;
    const whole = (path, value) => (has(value) ? shown(props.known, path, Math.floor(value).toLocaleString()) : null);
    const units = inOrder(Object.keys(props.state?.units || kd.units || {}), props.state?.order?.units)
        .filter((key) => key !== "engineers" && (!props.state?.units?.[key]?.project || kd.units?.[key]));
    return (
        <div className="status-kingdom-content kd-facts">
            <FactCard title="Kingdom">
                <Fact label="Race">{kd.race}</Fact>
                <Fact label="Networth">{whole("networth", kd.networth)}</Fact>
                <Fact label="Stars">{whole("stars", kd.stars)}</Fact>
            </FactCard>
            <FactCard title="Economy">
                <Fact label="Population">{whole("population", kd.population)}</Fact>
                <Fact label="Fuel">{whole("fuel", kd.fuel)}</Fact>
                <Fact label="Money">{whole("money", kd.money)}</Fact>
            </FactCard>
            <FactCard title="Operations">
                <Fact label="Engineers">{whole("units.engineers", kd.units?.engineers)}</Fact>
                <Fact label="Drones">{has(kd.drones) ? <>{whole("drones", kd.drones)}{props.actions?.("drones", true)}</> : props.actions?.("drones", true)}</Fact>
                <Fact label="Spy attempts">{whole("spy_attempts", kd.spy_attempts)}</Fact>
            </FactCard>
            <FactCard title="Army">
                {units.map((key) => (
                    <Fact key={key} label={props.state?.pretty_names?.[key] || key}>{whole(`units.${key}`, kd.units?.[key])}</Fact>
                ))}
            </FactCard>
            <FactCard title="Missiles">
                <Fact label="Planet Busters">{whole("missiles.planet_busters", kd.missiles?.planet_busters)}</Fact>
                <Fact label="Star Busters">{whole("missiles.star_busters", kd.missiles?.star_busters)}</Fact>
                <Fact label="Galaxy Busters">{whole("missiles.galaxy_busters", kd.missiles?.galaxy_busters)}</Fact>
            </FactCard>
        </div>
    );
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


function Military(props) {
    const units = props.kingdom?.units;
    const generals = props.kingdom?.generals_out || [];
    // Every unit the game has (in the server's order), shown when this kingdom has some or the units are revealed.
    const unitKeys = inOrder(Object.keys(props.state?.units || units || {}), props.state?.order?.units).filter((key) => key !== "engineers");
    const label = (key) => props.state?.pretty_names?.[key] || key;
    const count = (value) => (value ? value.toLocaleString() : null);
    // Generals out are part of the military snapshot as a whole.
    const generalsEnded = props.known?.endedOf("generals_out");
    return (
        <div className="military">
            <div className="table-scroll">
            <Table hover className="army-table" size="sm">
                <thead>
                    <tr>
                    <th colSpan={2}></th>
                    <th colSpan={Math.max(generals.length, 1)}>Generals</th>
                    </tr>
                </thead>
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Home</th>
                        {generals.length
                            ? generals.map((general, index) => <th key={index} style={{textAlign: "right"}}>{getTimeString(general.return_time)}</th>)
                            : <th />}
                    </tr>
                </thead>
                <tbody>
                    {unitKeys.map((key) => (
                        <tr key={key}>
                            <td style={{textAlign: "left"}}>{label(key)}</td>
                            <td style={{textAlign: "right"}}>{shown(props.known, `units.${key}`, count(units?.[key]))}</td>
                            {generals.length
                                ? generals.map((general, index) => <td key={index} style={{textAlign: "right"}}><Known ended={generalsEnded} gameConfig={props.known?.gameConfig}>{count(general[key])}</Known></td>)
                                : <td />}
                        </tr>
                    ))}
                </tbody>
            </Table>
            </div>
        </div>
    )
}
function Structures(props) {
    const structures = props.kingdom?.structures;
    return (
        
        <div className="kingdom-structures-info">
            <div className="table-scroll kd-narrow">
            <Table hover size="sm">
                <thead>
                    <tr>
                    <th style={{textAlign: "left"}}>Structure</th>
                    <th style={{textAlign: "right"}}>#</th>
                    <th style={{textAlign: "right"}}>%</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Homes</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.homes", structures?.homes?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.homes != undefined ? displayPercent((structures?.homes || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Mines</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.mines", structures?.mines?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.mines != undefined ? displayPercent((structures?.mines || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Fuel Plants</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.fuel_plants", structures?.fuel_plants?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.fuel_plants != undefined ? displayPercent((structures?.fuel_plants || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Hangars</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.hangars", structures?.hangars?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.hangars != undefined ? displayPercent((structures?.hangars || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Drone Factories</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.drone_factories", structures?.drone_factories?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.drone_factories != undefined ? displayPercent((structures?.drone_factories || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missile Silos</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.missile_silos", structures?.missile_silos?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.missile_silos != undefined ? displayPercent((structures?.missile_silos || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Workshops</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, "structures.workshops", structures?.workshops?.toLocaleString() || null)}</td>
                        <td style={{textAlign: "right"}}>{structures?.workshops != undefined ? displayPercent((structures?.workshops || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                </tbody>
            </Table>
            </div>
        </div>
    )
}

function Projects(props) {
    const kingdom = props.kingdom || {};
    if (kingdom.projects_assigned === undefined) {
        return <p className="kd-not-revealed">Not revealed. Spy on their projects to see them.</p>;
    }
    const projects = props.state?.projects || Object.fromEntries(Object.keys(kingdom.projects_points || {}).map((key) => [key, { name: key }]));
    const completed = kingdom.completed_projects || [];
    const rows = entriesInOrder(projects, props.state?.order?.projects)
        .filter(([, project]) => !project.race || project.race === kingdom.race)
        .map(([key, project]) => ({ key, ...project }));
    const continuous = rows.filter((row) => row.max_bonus !== undefined);
    const oneTime = rows.filter((row) => row.max_bonus === undefined);
    const points = (key) => `${Math.floor(kingdom.projects_points?.[key] || 0).toLocaleString()} / ${Math.floor(kingdom.projects_max_points?.[key] || 0).toLocaleString()}`;
    const done = (key) => (completed.indexOf(key) >= 0
        ? "Completed"
        : displayPercent(Math.min((kingdom.projects_points?.[key] || 0) / (kingdom.projects_max_points?.[key] || 1), 1)));
    const table = (title, list, lastHeader, last) => (
        <div className="panel kd-projects">
        <h3 className="panel-title">{title}</h3>
        <div className="table-scroll">
        <Table className="projects-table" hover size="sm">
            <thead>
                <tr>
                    <th style={{textAlign: "left"}}>Project</th>
                    <th className="assigned-col" style={{textAlign: "right"}}>Assigned</th>
                    <th style={{textAlign: "right"}}>Points</th>
                    <th style={{textAlign: "right"}}>{lastHeader}</th>
                </tr>
            </thead>
            <tbody>
                {list.map((row) => (
                    <tr key={row.key} className={completed.indexOf(row.key) >= 0 ? "disabled-table-row" : undefined}>
                        <td style={{textAlign: "left"}}>{row.name}</td>
                        <td className="assigned-col" style={{textAlign: "right"}}>{(kingdom.projects_assigned?.[row.key] || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{shown(props.known, `projects_points.${row.key}`, points(row.key))}</td>
                        <td style={{textAlign: "right"}}>{last(row.key)}</td>
                    </tr>
                ))}
            </tbody>
        </Table>
        </div>
        </div>
    );
    return (
        <div className="projects kd-projects-grid">
            {table("Continuous Projects", continuous, "Bonus",
                (key) => `${displayPercent(kingdom.current_bonuses?.[key] || 0)} / ${displayPercent(kingdom.max_bonuses?.[key] || 0)}`)}
            {table("One-Time Projects", oneTime, "% Completed", done)}
        </div>
    )
}

function Shields(props) {

    return (
        <div className="shields">
            {
                props.kingdom?.shields?.military != undefined
                ? <div className="table-scroll kd-narrow"><Table className="shields-table" hover size="sm">
                    <thead>
                        <tr>
                            <th style={{textAlign: "left"}}>Shield</th>
                            <th style={{textAlign: "right"}}>Current %</th>
                            <th style={{textAlign: "right"}}>Max %</th>
                            <th style={{textAlign: "right"}}>Current Power Cost</th>
                            <th style={{textAlign: "right"}}>Max Power Cost</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style={{textAlign: "left"}}>Military</td>
                            <td style={{textAlign: "right"}}>{shown(props.known, "shields.military", displayPercent(props.kingdom?.shields?.military || 0))}</td>
                            <td style={{textAlign: "right"}}>{displayPercent(props.shields?.desc?.military?.max || 0)}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.kingdom?.shields?.military * props.shields?.desc?.military?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.shields?.desc?.military?.max * props.shields?.desc?.military?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td style={{textAlign: "left"}}>Spy</td>
                            <td style={{textAlign: "right"}}>{shown(props.known, "shields.spy", displayPercent(props.kingdom?.shields?.spy || 0))}</td>
                            <td style={{textAlign: "right"}}>{displayPercent(props.shields?.desc?.spy?.max || 0)}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.kingdom?.shields?.spy * props.shields?.desc?.spy?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.shields?.desc?.spy?.max * props.shields?.desc?.spy?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td style={{textAlign: "left"}}>Spy Radar</td>
                            <td style={{textAlign: "right"}}>{shown(props.known, "shields.spy_radar", displayPercent(props.kingdom?.shields?.spy_radar || 0))}</td>
                            <td style={{textAlign: "right"}}>{displayPercent(props.shields?.desc?.spy_radar?.max || 0)}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.kingdom?.shields?.spy_radar * props.shields?.desc?.spy_radar?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.shields?.desc?.spy_radar?.max * props.shields?.desc?.spy_radar?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                        </tr>
                        <tr>
                            <td style={{textAlign: "left"}}>Missiles</td>
                            <td style={{textAlign: "right"}}>{shown(props.known, "shields.missiles", displayPercent(props.kingdom?.shields?.missiles || 0))}</td>
                            <td style={{textAlign: "right"}}>{displayPercent(props.shields?.desc?.missiles?.max || 0)}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.kingdom?.shields?.missiles * props.shields?.desc?.missiles?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{Math.floor(props.shields?.desc?.missiles?.max * props.shields?.desc?.missiles?.cost * props.kingdom?.stars * 100 || 0).toLocaleString()}</td>
                        </tr>
                    </tbody>
                </Table></div>
                : <p className="kd-not-revealed">Not revealed. Spy on their shields to see them.</p>
            }
        </div>
    )
}

export default KingdomContent;