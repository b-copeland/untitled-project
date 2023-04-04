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
                    <span className="text-box-item-title">Stars</span>
                    <span className="text-box-item-value">{props.kingdom?.stars?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Population</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom?.population).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Fuel</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom?.fuel).toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{props.kingdom?.units?.engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Drones</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom?.drones).toLocaleString()}</span>
                </div>
                <br />
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
                        <td style={{textAlign: "right"}}>{units?.recruits || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.recruits?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.recruits?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.recruits?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.recruits?.toLocaleString() || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Attackers</td>
                        <td style={{textAlign: "right"}}>{units?.attack || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.attack?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.attack?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.attack?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.attack?.toLocaleString() || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Defenders</td>
                        <td style={{textAlign: "right"}}>{units?.defense || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.defense?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.defense?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.defense?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.defense?.toLocaleString() || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Flexers</td>
                        <td style={{textAlign: "right"}}>{units?.flex || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.flex?.toLocaleString() || 0}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Big Flexers</td>
                        <td style={{textAlign: "right"}}>{units?.big_flex || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_0?.big_flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_1?.big_flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_2?.big_flex?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{generals.general_3?.big_flex?.toLocaleString() || 0}</td>
                    </tr>
                </tbody>
            </Table>
        </div>
    )
}
function Structures(props) {
    const structures = props.kingdom?.structures;
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
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
                        <td style={{textAlign: "right"}}>{structures?.homes?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.homes || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Mines</td>
                        <td style={{textAlign: "right"}}>{structures?.mines?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.mines || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Fuel Plants</td>
                        <td style={{textAlign: "right"}}>{structures?.fuel_plants?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.fuel_plants || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Hangars</td>
                        <td style={{textAlign: "right"}}>{structures?.hangars?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.hangars || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Drone Factories</td>
                        <td style={{textAlign: "right"}}>{structures?.drone_factories?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.drone_factories || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missile Silos</td>
                        <td style={{textAlign: "right"}}>{structures?.missile_silos?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.missile_silos || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Workshops</td>
                        <td style={{textAlign: "right"}}>{structures?.workshops?.toLocaleString() || 0}</td>
                        <td style={{textAlign: "right"}}>{displayPercent((structures?.workshops || 0) / (props.kingdom?.stars || 1))}</td>
                    </tr>
                </tbody>
            </Table>
        </div>
    )
}

export default KingdomContent;