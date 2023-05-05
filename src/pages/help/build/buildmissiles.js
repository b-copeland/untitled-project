import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function BuildMissiles(props) {
    const prettyNames = props.state.pretty_names || {};
    const missilesDesc = props.state.missiles || {};
    const missilesRows = Object.keys(missilesDesc).map((missilesKey, iter) => {
        return <tr key={"missiles_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[missilesKey]}</td>
            <td style={{textAlign: "right"}}>{missilesDesc[missilesKey].cost}</td>
            <td style={{textAlign: "right"}}>{missilesDesc[missilesKey].fuel_cost}</td>
            <td style={{textAlign: "right"}}>{missilesDesc[missilesKey].stars_damage}</td>
            <td style={{textAlign: "right"}}>{missilesDesc[missilesKey].fuel_damage}</td>
            <td style={{textAlign: "right"}}>{missilesDesc[missilesKey].pop_damage}</td>
        </tr>
    })
    return (
        <div id="buildmissiles" className="help-section">
            <h2>Build - Missiles</h2>
            <p>
                You can build up to {props.state.game_config?.BASE_MISSILE_SILO_CAPACITY} missiles per Missile Silo that you own.
            </p>
            <Table className="missiles-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th>Missile</th>
                        <th>Cost</th>
                        <th>Fuel Cost</th>
                        <th>Stars Damage</th>
                        <th>Fuel Damage</th>
                        <th>Pop Damage</th>
                    </tr>
                </thead>
                <tbody>
                    {missilesRows}
                </tbody>
            </Table>
        </div>
    )
}

export default BuildMissiles;