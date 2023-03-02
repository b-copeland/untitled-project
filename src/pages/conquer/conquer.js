import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Modal from 'react-bootstrap/Modal';
import "./conquer.css";
import Galaxy from "../galaxy.js";
import Attack from "./attack.js";
import Spy from "./spy.js";
import LaunchMissiles from "./launchmissiles.js";
import Message from "../message.js";


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
            data={props.data}
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
    const [showAttack, setShowAttack] = useState(false);
    const [showSpy, setShowSpy] = useState(false);
    const [showMissile, setShowMissile] = useState(false);
    const [showMessage, setShowMessage] = useState(false);
    const [showGalaxy, setShowGalaxy] = useState(false);
    const [galaxyToShow, setGalaxyToShow] = useState('');

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
                <Button className="inline-galaxy-button" variant="primary" type="submit" onClick={() => setShowAttack(true)}>
                    Attack
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" onClick={() => setShowSpy(true)}>
                    Spy
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" onClick={() => setShowMissile(true)}>
                    Missile
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" onClick={() => setShowMessage(true)}>
                    Message
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" onClick={() => {setGalaxyToShow(props.galaxies_inverted[kdId] || ""); setShowGalaxy(true);}}>
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
            <Modal
                show={showAttack}
                onHide={() => setShowAttack(false)}
                animation={false}
                dialogClassName="attack-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Attack</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Attack data={props.data}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowAttack(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Modal
                show={showSpy}
                onHide={() => setShowSpy(false)}
                animation={false}
                dialogClassName="spy-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Spy</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Spy data={props.data}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowSpy(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Modal
                show={showMissile}
                onHide={() => setShowMissile(false)}
                animation={false}
                dialogClassName="missile-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Missile</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <LaunchMissiles data={props.data}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowMissile(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Modal
                show={showMessage}
                onHide={() => setShowMessage(false)}
                animation={false}
                dialogClassName="message-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Message</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Message data={props.data}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowMessage(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Modal
                show={showGalaxy}
                onHide={() => setShowGalaxy(false)}
                animation={false}
                dialogClassName="galaxy-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>View Galaxy</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Galaxy data={props.data} initialGalaxyId={galaxyToShow}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowGalaxy(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
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