import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./kingdominfo.css";


function KingdomContent(props) {
    const [key, setKey] = useState('kingdom');

    return (
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="kingdom" title="Kingdom">
          <Kingdom kingdom={props.data.kingdom} kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} kdId={props.data.kdId}/>
        </Tab>
        <Tab eventKey="military" title="Military">
          <Military kingdom={props.data.kingdom} />
        </Tab>
        <Tab eventKey="structures" title="Structures">
          <Structures kingdom={props.data.kingdom}/>
        </Tab>
      </Tabs>
    );
}

function Kingdom(props) {
    
    return (
        <div className="status">
            <div className="text-box kingdom-card">
                <h4>{props.kingdoms[props.kdId] || ""} ({props.galaxies_inverted[props.kdId] || ""})</h4>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Name</span>
                    <span className="text-box-item-value">{props.kingdoms[props.kdId] || ""}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Race</span>
                    <span className="text-box-item-value">{props.kingdom?.race}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Networth</span>
                    <span className="text-box-item-value">{props.kingdom?.networth?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Stars</span>
                    <span className="text-box-item-value">{props.kingdom?.stars?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value">{props.kingdom?.population != undefined ? Math.floor(props.kingdom?.population).toLocaleString() : null}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value">{props.kingdom?.fuel != undefined ? Math.floor(props.kingdom?.fuel).toLocaleString() : null}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Money</span>
                    <span className="text-box-item-value">{props.kingdom?.money != undefined ? Math.floor(props.kingdom?.money).toLocaleString() : null}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value">{props.kingdom?.drones != undefined ? Math.floor(props.kingdom?.drones).toLocaleString() : null}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Spy Attempts</span>
                    <span className="text-box-item-value">{props.kingdom?.spy_attempts?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruits</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.recruits?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Attackers</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.attack?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Defenders</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.defense?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Flexers</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.flex?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Big Flexers</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.big_flex?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Planet Busters</span>
                    <span className="text-box-item-value">{props.kingdom?.missiles?.planet_busters?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Star Busters</span>
                    <span className="text-box-item-value">{props.kingdom?.missiles?.star_busters?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Galaxy Busters</span>
                    <span className="text-box-item-value">{props.kingdom?.missiles?.galaxy_busters?.toLocaleString()}</span>
                </div>
            </div>
        </div>
    )
}

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}


function Military(props) {
    const units = props.kingdom?.units;
    // const generals = props.kingdom.generals_out.map((general, index) => {
    //     const keyName = "general_" + index;
    //     return {[keyName]: general}
    // })
    function arrayToObject(arr, keyPrefix="general_") {
        var rv = {};
        for (var i = 0; i < arr.length; ++i)
          rv[keyPrefix + i] = arr[i];
        return rv;
      };
    const generals = arrayToObject(props.kingdom?.generals_out || []);
    return (
        <div className="military">
            <h2>Armies</h2>
            <Table striped bordered hover>
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
                        <th style={{textAlign: "right"}}>{getTimeString(generals.general_0?.return_time)}</th>
                        <th style={{textAlign: "right"}}>{getTimeString(generals.general_1?.return_time)}</th>
                        <th style={{textAlign: "right"}}>{getTimeString(generals.general_2?.return_time)}</th>
                        <th style={{textAlign: "right"}}>{getTimeString(generals.general_3?.return_time)}</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Recruits</td>
                        <td style={{textAlign: "right"}}>{units?.recruits || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.recruits?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.recruits?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.recruits?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.recruits?.toLocaleString() || null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Attackers</td>
                        <td style={{textAlign: "right"}}>{units?.attack || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.attack?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.attack?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.attack?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.attack?.toLocaleString() || null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Defenders</td>
                        <td style={{textAlign: "right"}}>{units?.defense || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.defense?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.defense?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.defense?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.defense?.toLocaleString() || null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Flexers</td>
                        <td style={{textAlign: "right"}}>{units?.flex || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.flex?.toLocaleString() || null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Big Flexers</td>
                        <td style={{textAlign: "right"}}>{units?.big_flex || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.big_flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.big_flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.big_flex?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.big_flex?.toLocaleString() || null}</td>
                    </tr>
                </tbody>
            </Table>
        </div>
    )
}
function Structures(props) {
    const structures = props.kingdom?.structures;
    const displayPercent = (percent) => percent != null ? `${(percent * 100).toFixed(1)}%` : null;
    return (
        
        <div className="kingdom-structures-info">
            <Table striped bordered hover>
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
                        <td style={{textAlign: "right"}}>{structures?.homes?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.homes != undefined ? displayPercent((structures?.homes || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Mines</td>
                        <td style={{textAlign: "right"}}>{structures?.mines?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.mines != undefined ? displayPercent((structures?.mines || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Fuel Plants</td>
                        <td style={{textAlign: "right"}}>{structures?.fuel_plants?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.fuel_plants != undefined ? displayPercent((structures?.fuel_plants || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Hangars</td>
                        <td style={{textAlign: "right"}}>{structures?.hangars?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.hangars != undefined ? displayPercent((structures?.hangars || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Drone Factories</td>
                        <td style={{textAlign: "right"}}>{structures?.drone_factories?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.drone_factories != undefined ? displayPercent((structures?.drone_factories || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missile Silos</td>
                        <td style={{textAlign: "right"}}>{structures?.missile_silos?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.missile_silos != undefined ? displayPercent((structures?.missile_silos || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Workshops</td>
                        <td style={{textAlign: "right"}}>{structures?.workshops?.toLocaleString() || null}</td>
                        <td style={{textAlign: "right"}}>{structures?.workshops != undefined ? displayPercent((structures?.workshops || 0) / (props.kingdom?.stars || 1)) : null}</td>
                    </tr>
                </tbody>
            </Table>
        </div>
    )
}

export default KingdomContent;