import React, { useEffect, useState } from "react";
import {
    useSearchParams,
    useNavigate,
  } from "react-router-dom";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./galaxy.css"

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}

function Galaxy(props) {
    const [galaxyInfo, setGalaxyInfo] = useState({});
    const [galaxyIndex, setGalaxyIndex] = useState();
    const [galaxiesArray, setGalaxiesArray] = useState([]);
    const [clusterInput, setClusterInput] = useState();
    const [galaxyInput, setGalaxyInput] = useState();

    useEffect(() => {
        const fetchData = async () => {
            if (galaxiesArray.length === 0) {
                await authFetch("api/galaxies").then(r => r.json()).then(r => setGalaxiesArray(Object.keys(r).sort()));
            };
            if (galaxyIndex != undefined) {
                if (galaxiesArray[galaxyIndex] != undefined) {
                    await authFetch("api/galaxy/" + galaxiesArray[galaxyIndex]).then(r => r.json()).then(r => setGalaxyInfo(r));
                }
            };
        }
        fetchData();
    }, [galaxyIndex])
    if ((galaxyIndex === undefined) & galaxiesArray.length > 0) {
        var newIndex = galaxiesArray.indexOf(props.initialGalaxyId || '1:1');
        setGalaxyIndex(newIndex);
        setClusterInput(galaxiesArray[newIndex].split(':')[0]);
        setGalaxyInput(galaxiesArray[newIndex].split(':')[1]);
    };
    if (Object.keys(galaxyInfo).length === 0) {
        return null;
    }

    const moveLeft = (e)=>{
        if (galaxyIndex === -1) {  
            setGalaxyIndex(galaxiesArray.length - 1);
            setClusterInput(galaxiesArray[galaxiesArray.length - 1].split(':')[0]);
            setGalaxyInput(galaxiesArray[galaxiesArray.length - 1].split(':')[1]);
            return;
        }
        if (galaxyIndex === 0) {
            var newIndex = galaxiesArray.length - 1;
        } else {
            var newIndex = galaxyIndex - 1;
        }
        setGalaxyIndex(newIndex);
        setClusterInput(galaxiesArray[newIndex].split(':')[0]);
        setGalaxyInput(galaxiesArray[newIndex].split(':')[1]);
    }
    const moveRight = (e)=>{
        if (galaxyIndex === -1) {  
            setGalaxyIndex(0);
            setClusterInput(galaxiesArray[0].split(':')[0]);
            setGalaxyInput(galaxiesArray[0].split(':')[1]);
            return;
        }
        if (galaxyIndex === (galaxiesArray.length - 1)) {
            var newIndex = 0;
        } else {
            var newIndex = galaxyIndex + 1;
        }
        setGalaxyIndex(newIndex);
        setClusterInput(galaxiesArray[newIndex].split(':')[0]);
        setGalaxyInput(galaxiesArray[newIndex].split(':')[1]);
    }
    const handleClusterInput = (e) => {
        if (e.target.value) {
            setClusterInput(e.target.value);
            setGalaxyIndex(galaxiesArray.indexOf(e.target.value + ":" + galaxyInput));
        } else {
            setClusterInput(e.target.value);
        }
    }
    const handleGalaxyInput = (e) => {
        if (e.target.value) {
            setGalaxyInput(e.target.value)
            setGalaxyIndex(galaxiesArray.indexOf(clusterInput + ":" + e.target.value));
        } else {
            setGalaxyInput(e.target.value);
        }
    }
    const galaxyRows = Object.keys(galaxyInfo).map((kdId) =>
        <tr key={kdId}>
            <td>{galaxyInfo[kdId].name || ""}</td>
            <td>{galaxyInfo[kdId].race || ""}</td>
            <td>{galaxyInfo[kdId].stars || ""}</td>
            <td>{galaxyInfo[kdId].score || ""}</td>
            <td>{galaxyInfo[kdId].aggression || ""}</td>
            <td>07:59:59</td>
            <td>Growth, Active</td>
            <td>
                <Button variant="primary" type="submit">
                    Attack
                </Button>
                <Button variant="primary" type="submit">
                    Spy
                </Button>
                <Button variant="primary" type="submit">
                    Missile
                </Button>
                <Button variant="primary" type="submit">
                    Message
                </Button>
            </td>
        </tr>
    );
    return (
        <div className="galaxy">
            <div className="galaxy-nav-container">
                <span className="galaxy-nav-arrow" onClick={moveLeft}>{'<<'}</span>
                <div className="galaxy-nav-input">
                    <InputGroup className="galaxy-nav-input-form">
                        <InputGroup.Text id="cluster">Cluster</InputGroup.Text>
                        <Form.Control
                        // placeholder="Username"
                        aria-label="Cluster"
                        onChange={handleClusterInput}
                        value={clusterInput || ''} 
                        />
                    </InputGroup>
                    <InputGroup className="galaxy-nav-input-form">
                        <InputGroup.Text id="galaxy">Galaxy</InputGroup.Text>
                        <Form.Control
                        // placeholder="Username"
                        aria-label="Galaxy"
                        onChange={handleGalaxyInput}
                        value={galaxyInput || ''} 
                        />
                    </InputGroup>
                </div>
                <span className="galaxy-nav-arrow" onClick={moveRight}>{'>>'}</span>
            </div>
            {!(galaxiesArray[galaxyIndex] != undefined)
                ? <h3>This galaxy does not exist!</h3>
                : <Table striped bordered hover>
                    <thead>
                        <tr>
                        <th>Kingdom</th>
                        <th>Race</th>
                        <th>Stars</th>
                        <th>Score</th>
                        <th>Aggression</th>
                        <th>Return Time</th>
                        <th>Status</th>
                        <th colSpan={5}>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {galaxyRows}
                    </tbody>
                </Table>
            }
        </div>
    );
}

export default Galaxy;