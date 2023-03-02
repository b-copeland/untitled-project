import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Modal from 'react-bootstrap/Modal';
import "./conquer.css";


function ConquerContent(props) {
    const [key, setKey] = useState('kingdom');

    return (
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="revealed"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="revealed" title="Revealed">
          <Revealed
            revealed={props.data.revealed}
            kingdoms={props.data.kingdoms}
            galaxies_inverted={props.data.galaxies_inverted}
            empires={props.data.empires}
            empires_inverted={props.data.empires_inverted}
            loading={props.loading}
            updateData={props.updateData}
            />
        </Tab>
        <Tab eventKey="shared" title="Shared">
          <Shared kingdom={props.data.kingdom} kingdoms={props.data.kingdoms}/>
        </Tab>
        <Tab eventKey="pinned" title="Pinned">
          <Pinned kingdom={props.data.kingdom} loading={props.loading} updateData={props.updateData} />
        </Tab>
      </Tabs>
    );
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

function Revealed(props) {
    const [maxKdInfo, setMaxKdInfo] = useState({});

    useEffect(() => {
        const fetchData = async () => {
            if (Object.keys(props.revealed).length > 0) {
                if (Object.keys(props.revealed.revealed).length > 0) {
                    const opts = {"kingdoms": Object.keys(props.revealed.revealed)}
                    await authFetch("api/kingdomsinfo", {
                        method: "POST",
                        body: JSON.stringify(opts)
                    }).then(r => r.json()).then(r => setMaxKdInfo(r));
                }
            };
        }
        fetchData();
    }, [props.revealed])
    if (Object.keys(props.revealed).length === 0) {
        return <h3>Loading...</h3>
    }

    const onSubmitClick = (e)=>{
        const updateFunc = () => authFetch('api/revealrandomgalaxy')
        props.updateData(['revealed', 'kingdom'], [updateFunc])
    }
    
    const getRemainingSpans = (kdId, revealed) => {
        const remainingSpans = Object.keys(revealed[kdId]).map((category) =>
            <div key={kdId.toString() + '_' + category} className="remaining-timer">
                <span className="remaining-time-title">{category}</span>
                <span className="remaining-time-value">{getTimeString(revealed[kdId][category])}</span>
                <br />
            </div>
        )
        return remainingSpans;
    }
    const revealedRows = Object.keys(props.revealed.revealed).map((kdId) =>
        <tr key={kdId}>
            <td>{getRemainingSpans(kdId, props.revealed.revealed)}</td>
            <td>{props.kingdoms[kdId] || ""}</td>
            <td>{props.galaxies_inverted[kdId] || ""}</td>
            <td>{props.empires[props.empires_inverted?.empires_inverted[kdId]].name || ""}</td>
            <td>{maxKdInfo[kdId]?.stars || ""}</td>
            <td>{maxKdInfo[kdId]?.score || ""}</td>
            <td>
                <Button className="inline-galaxy-button" variant="primary" type="submit">
                    Attack
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit">
                    Spy
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit">
                    Missile
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit">
                    Message
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit">
                    View Galaxy
                </Button>
            </td>
        </tr>
    );
    const revealedGalaxyRows = Object.keys(props.revealed.galaxies).map((galaxyId) =>
        <tr key={galaxyId}>
            <td>{getTimeString(props.revealed.galaxies[galaxyId])}</td>
            <td>{galaxyId || ""}</td>
            <td>{props.empires[props.empires_inverted?.galaxy_empires[galaxyId]].name || ""}</td>
        </tr>
    );
    return (
        <div className="revealed">
           {
                props.loading.revealed
                ? <Button className="reveal-random-galaxy-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="reveal-random-galaxy-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Reveal Random Galaxy (1 Spy Attempt)
                </Button>
           }
            <Table className="revealed-table" striped bordered hover>
                <thead>
                    <tr>
                        <th>Remaining</th>
                        <th>Kingdom</th>
                        <th>Galaxy</th>
                        <th>Empire</th>
                        <th>Stars</th>
                        <th>Score</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {revealedRows}
                </tbody>
            </Table>
            <Table className="revealed-table" striped bordered hover>
                <thead>
                    <tr>
                        <th>Remaining</th>
                        <th>Galaxy</th>
                        <th>Empire</th>
                    </tr>
                </thead>
                <tbody>
                    {revealedGalaxyRows}
                </tbody>
            </Table>
        </div>
    )
}

function Shared(props) {
    return (
        <div className="conquer">
            <Button className="reveal-random-galaxy-button" variant="primary" type="submit">
                Reveal Random Galaxy
            </Button>
        </div>
    )
}

function Pinned(props) {
    return (
        <div className="conquer">
            <Button className="reveal-random-galaxy-button" variant="primary" type="submit">
                Reveal Random Galaxy
            </Button>
        </div>
    )
}

export default ConquerContent;