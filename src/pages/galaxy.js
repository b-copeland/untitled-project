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
import Modal from 'react-bootstrap/Modal';
import "./galaxy.css";
import Kingdom from "./kingdominfo.js";
import Attack from "./conquer/attack.js";
import Spy from "./conquer/spy.js";
import LaunchMissiles from "./conquer/launchmissiles.js";
import Message from "./message.js";
import Header from "../components/header";

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
    // const [galaxiesArray, setGalaxiesArray] = useState(Object.keys(props.data.galaxies));
    const [clusterInput, setClusterInput] = useState();
    const [galaxyInput, setGalaxyInput] = useState();
    const [loading, setLoading] = useState(false);
    const [showView, setShowView] = useState(false);
    const [showAttack, setShowAttack] = useState(false);
    const [showSpy, setShowSpy] = useState(false);
    const [showMissile, setShowMissile] = useState(false);
    const [showMessage, setShowMessage] = useState(false);
    const [showShareInfo, setShowShareInfo] = useState(false);
    const [kdToShow, setKdToShow] = useState();

    const galaxiesArray = Object.keys(props.data.galaxies);
    useEffect(() => {
        const fetchData = async () => {
            if (galaxyIndex != undefined) {
                if (galaxiesArray[galaxyIndex] != undefined) {
                    await authFetch("api/galaxy/" + galaxiesArray[galaxyIndex]).then(r => r.json()).then(r => setGalaxyInfo(r));
                    setLoading(false);
                }
            };
        }
        fetchData();
    }, [galaxyIndex]);
    if ((galaxyIndex === undefined) & galaxiesArray.length > 0) {
        var newIndex = galaxiesArray.indexOf(props.initialGalaxyId || '1:1');
        setGalaxyIndex(newIndex);
        setClusterInput(galaxiesArray[newIndex].split(':')[0]);
        setGalaxyInput(galaxiesArray[newIndex].split(':')[1]);
    };
    if (galaxyIndex === undefined) {
        return <h3>Loading...</h3>;
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
        setLoading(true);
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
        setLoading(true);
    }
    const handleClusterInput = (e) => {
        if (e.target.value) {
            setClusterInput(e.target.value);
            setGalaxyIndex(galaxiesArray.indexOf(e.target.value + ":" + galaxyInput));
            setLoading(true);
        } else {
            setClusterInput(e.target.value);
        }
    }
    const handleGalaxyInput = (e) => {
        if (e.target.value) {
            setGalaxyInput(e.target.value)
            setGalaxyIndex(galaxiesArray.indexOf(clusterInput + ":" + e.target.value));
            setLoading(true);
        } else {
            setGalaxyInput(e.target.value);
        }
    }

    const onSubmitPin = (e)=>{
        const updateFunc = () => authFetch('api/pinned', {
            body: JSON.stringify({"pinned": [e.target.name]}),
            method: "POST", 
        })
        props.updateData(['pinned'], [updateFunc])
    }

    const onSubmitUnpin = (e)=>{
        const updateFunc = () => authFetch('api/pinned', {
            body: JSON.stringify({"unpinned": [e.target.name]}),
            method: "POST", 
        })
        props.updateData(['pinned'], [updateFunc])
    }

    const onSubmitShare = (e)=>{
        const updateFunc = () => authFetch('api/share/' + kdToShow, {
            method: "POST", 
        })
        props.updateData(['revealed'], [updateFunc]);
        setShowShareInfo(false);
    }

    const onSubmitUnShare = (kdId)=>{
        const updateFunc = () => authFetch('api/unshare/' + kdId, {
            method: "POST", 
        })
        props.updateData(['revealed'], [updateFunc])
    }
    const calcCoordinateDistance = (coord_a, coord_b) => {

        const direct_distance = Math.abs(coord_a - coord_b)
        const indirect_distance_1 = (coord_a) + (99 - coord_b)
        const indirect_distance_2 = (coord_b) + (99 - coord_a)
        return Math.min(direct_distance, indirect_distance_1, indirect_distance_2);
    }
    const galaxyRows = Object.keys(galaxyInfo).map((kdId) =>
        <tr key={kdId}>
            <td>{galaxyInfo[kdId].name || props.data.kingdoms[kdId] || ""}</td>
            <td>{galaxyInfo[kdId].race || ""}</td>
            <td style={{textAlign: "right"}}>{galaxyInfo[kdId].stars?.toLocaleString() || ""}</td>
            {/* <td style={{textAlign: "right"}}>{galaxyInfo[kdId].score != undefined ? Math.floor(galaxyInfo[kdId].score).toLocaleString() : ""}</td>
            <td style={{textAlign: "right"}}>{galaxyInfo[kdId].aggression || ""}</td> */}
            <td style={{textAlign: "right"}}>{calcCoordinateDistance(galaxyInfo[kdId].coordinate || 0, props.data.kingdom.coordinate || 0).toString().padStart(2, '0') + ' (' + (galaxyInfo[kdId].coordinate || 0).toString().padStart(2, '0') + ')'}</td>
            <td>{galaxyInfo[kdId].status}</td>
            <td>
                <Button className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowView(true)}}>
                    View
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowAttack(true)}}>
                    Attack
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowSpy(true)}}>
                    Spy
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowMissile(true)}}>
                    Missile
                </Button>
                <Button className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowMessage(true)}}>
                    Message
                </Button>
                {
                    props.loading.pinned
                    ? <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" disabled>
                        Loading...
                    </Button>
                    : props.data.pinned.indexOf(kdId) >= 0
                    ? <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={onSubmitUnpin}>
                        Unpin
                    </Button>
                    : <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={onSubmitPin}>
                        Pin
                    </Button>
                }
                {
                    props.data.galaxies_inverted[kdId] == props.data.galaxies_inverted[props.data.kingdom.kdId]
                    ? props.loading.revealed
                        ? <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" disabled>
                            Loading...
                        </Button>
                        : props.data.revealed.revealed_to_galaxymates?.indexOf(kdId) >= 0
                        ? <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => onSubmitUnShare(kdId)}>
                            Stop Sharing
                        </Button>
                        : <Button name={kdId} className="inline-galaxy-button" variant="primary" type="submit" size="sm" onClick={() => {setKdToShow(kdId); setShowShareInfo(true)}}>
                            Share 
                        </Button>
                    : null
                }
            </td>
        </tr>
    );
    const NonexistentGalaxy = () => {
        setLoading(false);
        return <h3>This galaxy does not exist!</h3>
    }
    return (
        <>
        <Header data={props.data} />
        <div className="galaxy">
            <Modal
                show={showView}
                onHide={() => setShowView(false)}
                animation={false}
                dialogClassName="view-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>View</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Kingdom data={{"kingdom": galaxyInfo[kdToShow], "kingdoms": props.data.kingdoms, "galaxies_inverted": props.data.galaxies_inverted, "kdId": kdToShow}}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowView(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
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
                    <Attack data={props.data} loading={props.loading} updateData={props.updateData} initialKd={kdToShow}/>
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
                    <Spy data={props.data} loading={props.loading} updateData={props.updateData} initialKd={kdToShow}/>
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
                    <LaunchMissiles data={props.data} loading={props.loading} updateData={props.updateData} initialKd={kdToShow}/>
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
                    <Message data={props.data} loading={props.loading} updateData={props.updateData} initialKd={kdToShow}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowMessage(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Modal
                show={showShareInfo}
                onHide={() => setShowShareInfo(false)}
                animation={false}
                dialogClassName="share-info-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Share Info?</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div>
                        <span>Sharing your info will allow the target kingdom to see all your kingdom info. You can stop sharing your info at any time</span>
                        <br />
                        <br />
                        <span>Are you sure?</span>
                        <br />
                        <br />
                        <Button variant="primary" type="submit" onClick={onSubmitShare}>
                            Share 
                        </Button>
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowShareInfo(false)}>
                    Cancel
                    </Button>
                </Modal.Footer>
            </Modal>
            {
                loading
                ? <div className="galaxy-nav-container">
                    <span className="galaxy-nav-arrow-disabled">{'<<'}</span>
                    <div className="galaxy-nav-input">
                        <InputGroup className="galaxy-nav-input-form">
                            <InputGroup.Text id="cluster">Cluster</InputGroup.Text>
                            <Form.Control
                            // placeholder="Username"
                            aria-label="Cluster"
                            onChange={handleClusterInput}
                            value={clusterInput || ''}
                            disabled
                            autoComplete="off"
                            />
                        </InputGroup>
                        <InputGroup className="galaxy-nav-input-form">
                            <InputGroup.Text id="galaxy">Galaxy</InputGroup.Text>
                            <Form.Control
                            // placeholder="Username"
                            aria-label="Galaxy"
                            onChange={handleGalaxyInput}
                            value={galaxyInput || ''} 
                            disabled
                            autoComplete="off"
                            />
                        </InputGroup>
                    </div>
                    <span className="galaxy-nav-arrow-disabled" >{'>>'}</span>
                </div>
                : <div className="galaxy-nav-container">
                    <span className="galaxy-nav-arrow" onClick={moveLeft}>{'<<'}</span>
                    <div className="galaxy-nav-input">
                        <InputGroup className="galaxy-nav-input-form">
                            <InputGroup.Text id="cluster">Cluster</InputGroup.Text>
                            <Form.Control
                            // placeholder="Username"
                            aria-label="Cluster"
                            onChange={handleClusterInput}
                            value={clusterInput || ''} 
                            autoComplete="off"
                            />
                        </InputGroup>
                        <InputGroup className="galaxy-nav-input-form">
                            <InputGroup.Text id="galaxy">Galaxy</InputGroup.Text>
                            <Form.Control
                            // placeholder="Username"
                            aria-label="Galaxy"
                            onChange={handleGalaxyInput}
                            value={galaxyInput || ''} 
                            autoComplete="off"
                            />
                        </InputGroup>
                    </div>
                    <span className="galaxy-nav-arrow" onClick={moveRight}>{'>>'}</span>
                </div>
            }
            
            {!(galaxiesArray[galaxyIndex] != undefined)
                ? <NonexistentGalaxy />
                : <Table striped bordered hover className="galaxies-table" size="sm" >
                    <thead>
                        <tr>
                        <th>Kingdom</th>
                        <th>Race</th>
                        <th style={{textAlign: "right"}}>Stars</th>
                        {/* <th style={{textAlign: "right"}}>Score</th>
                        <th style={{textAlign: "right"}}>Aggression</th> */}
                        <th style={{textAlign: "right"}}>Distance</th>
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
    </>
    );
}

export default Galaxy;