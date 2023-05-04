import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Scores(props) {
    const pointsRows = props.state.game_config?.NETWORTH_POINTS.map((points, iter) => {
        return <tr key={iter}>
            <td style={{textAlign: "left"}}>{iter + 1}</td>
            <td style={{textAlign: "right"}}>{points}</td>
        </tr>
    })
    return (
        <div id="scores" className="help-section">
            <h2>Scores</h2>
            <p>
                The scores page displays the current leaders in Points, Networth, or Stars. 
                The kingdom names in the Points ranking will always be hidden. Kingdoms in the 
                Networth or Stars ranking will be revealed if their stats are revealed to you.
            </p>
            <p>
                Points are allocated to continuously to networth leaders at the rate below 
                per {props.state.game_config?.BASE_EPOCH_SECONDS} seconds.
            </p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Networth Rank</th>
                        <th>Points</th>
                    </tr>
                </thead>
                <tbody>
                    {pointsRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Scores;