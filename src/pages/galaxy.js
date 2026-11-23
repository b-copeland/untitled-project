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
import ButtonGroup from 'react-bootstrap/ButtonGroup';
import "./galaxy.css";
import { tradable } from "./conquer/intel.js";
import { KingdomLink, kingdomPath, targetPath } from "../components/kingdomlink";
import { useFromHere } from "../components/pagehead";
import HelpButton from "../components/helpbutton";
import { IconButton } from "../components/iconbutton";
import { withLastKnown, Known } from "../components/lastknown";
import { BsEye, BsBinoculars, BsRocketTakeoff, BsChatDots, BsPinAngle, BsPinAngleFill, BsShare, BsShareFill, BsClipboardData, BsChevronLeft, BsChevronRight } from "react-icons/bs";
import { GiCrossedSwords } from "react-icons/gi";

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}

// Table or cards, remembered for next time. Storage can be unavailable (private windows), so it is only a convenience.
const VIEW_KEY = "galaxy-view";
// With nothing saved yet, a phone-sized screen starts on cards (the table scrolls sideways there) and a wide one on the table.
const savedView = () => {
    try {
        const saved = window.localStorage.getItem(VIEW_KEY);
        if (saved === "cards" || saved === "table") return saved;
    } catch (e) { /* no storage: use the screen */ }
    try { return window.matchMedia("(max-width: 767px)").matches ? "cards" : "table"; } catch (e) { return "table"; }
};

/** "3h" or "40m" until the date; the age of the intel on a kingdom is how long it has left. */
const timeLeft = (date) => {
    const minutes = Math.max((Date.parse(date) - Date.now()) / 60000, 0);
    return minutes >= 60 ? `${Math.floor(minutes / 60)}h` : `${Math.floor(minutes)}m`;
};

function Galaxy(props) {
    const [view, setViewState] = useState(savedView);
    const setView = (next) => {
        setViewState(next);
        try { window.localStorage.setItem(VIEW_KEY, next); } catch (e) { /* not remembered */ }
    };
    const [galaxyInfo, setGalaxyInfo] = useState({});
    const [galaxyIndex, setGalaxyIndex] = useState();
    // const [galaxiesArray, setGalaxiesArray] = useState(Object.keys(props.data.galaxies));
    const [clusterInput, setClusterInput] = useState();
    const [galaxyInput, setGalaxyInput] = useState();
    const [loading, setLoading] = useState(false);
    const [showShareInfo, setShowShareInfo] = useState(false);
    const [query] = useSearchParams();
    const navigate = useNavigate();
    const fromHere = useFromHere();
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
        // A galaxy chosen by the link here (/galaxy?galaxy=1:3, from Conquer), else your own.
        const asked = galaxiesArray.indexOf(query.get("galaxy") || "");
        var newIndex = asked >= 0 ? asked : galaxiesArray.indexOf(props.initialGalaxyId || '1:1');
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
    // What can be done to a kingdom from its row. Pin and share toggle, so the icon and label say what clicking does now.
    const kingdomActions = (kdId) => {
        const open = (show) => () => { setKdToShow(kdId); show(true); };
        // The kingdom and the planners are pages of their own, opened with this kingdom chosen; they link back here.
        const go = (path) => () => navigate(path, { state: fromHere });
        const pinned = props.data.pinned.indexOf(kdId) >= 0;
        const inYourGalaxy = props.data.galaxies_inverted[kdId] == props.data.galaxies_inverted[props.data.kingdom.kdId];
        const shared = props.data.revealed.revealed_to_galaxymates?.indexOf(kdId) >= 0;
        return [
            { icon: BsEye, label: "View", onClick: go(kingdomPath(kdId)) },
            { icon: GiCrossedSwords, label: "Attack", onClick: go(targetPath("/attack", kdId)) },
            { icon: BsBinoculars, label: "Spy", onClick: go(targetPath("/spy", kdId)) },
            { icon: BsRocketTakeoff, label: "Launch missiles", onClick: go(targetPath("/launchmissiles", kdId)) },
            { icon: BsChatDots, label: "Message", onClick: go(`/message?to=${kdId}`) },
            ...(tradable(props.data, kdId) ? [{ icon: BsClipboardData, label: "Intel: share, buy or ask for it", onClick: go(kingdomPath(kdId, "intel")) }] : []),
            pinned
                ? { icon: BsPinAngleFill, label: "Unpin", onClick: () => onSubmitUnpin({ target: { name: kdId } }), disabled: props.loading.pinned, active: true }
                : { icon: BsPinAngle, label: "Pin", onClick: () => onSubmitPin({ target: { name: kdId } }), disabled: props.loading.pinned },
            ...(inYourGalaxy
                ? [shared
                    ? { icon: BsShareFill, label: "Stop sharing your kingdom with them", onClick: () => onSubmitUnShare(kdId), disabled: props.loading.revealed, active: true }
                    : { icon: BsShare, label: "Share your kingdom with them", onClick: open(setShowShareInfo), disabled: props.loading.revealed }]
                : []),
        ];
    };
    const gameConfig = props.data.state?.game_config;
    // Each kingdom with what ended intel last showed where nothing is revealed now (components/lastknown.js).
    const known = Object.fromEntries(Object.keys(galaxyInfo).map((kdId) => [kdId, withLastKnown(galaxyInfo[kdId])]));
    // Unknown stays undefined, so the cards can say "?".
    const shown = (kdId, path, value) => (value === undefined || value === ""
        ? value
        : <Known ended={known[kdId].endedOf(path)} gameConfig={gameConfig}>{value}</Known>);
    const galaxyRows = Object.keys(galaxyInfo).map((kdId) =>
        <tr key={kdId}>
            <td><KingdomLink kdId={kdId} data={props.data}>{galaxyInfo[kdId].name || props.data.kingdoms[kdId] || ""}</KingdomLink></td>
            <td>{galaxyInfo[kdId].race || ""}</td>
            <td style={{textAlign: "right"}}>{shown(kdId, "stars", known[kdId].kingdom.stars?.toLocaleString() || "")}</td>
            {/* <td style={{textAlign: "right"}}>{galaxyInfo[kdId].networth != undefined ? Math.floor(galaxyInfo[kdId].networth).toLocaleString() : ""}</td>
            <td style={{textAlign: "right"}}>{galaxyInfo[kdId].aggression || ""}</td> */}
            <td style={{textAlign: "right"}}>{calcCoordinateDistance(galaxyInfo[kdId].coordinate || 0, props.data.kingdom.coordinate || 0).toString().padStart(2, '0') + ' (' + (galaxyInfo[kdId].coordinate || 0).toString().padStart(2, '0') + ')'}</td>
            <td>{galaxyInfo[kdId].status}</td>
            <td className="galaxy-actions" data-tour="galaxy-actions">
                {kingdomActions(kdId).map((action) => <IconButton key={action.label} {...action} />)}
            </td>
        </tr>
    );
    const kingdomFacts = (kdId) => ({
        name: galaxyInfo[kdId].name || props.data.kingdoms[kdId] || "",
        race: galaxyInfo[kdId].race || "",
        stars: shown(kdId, "stars", known[kdId].kingdom.stars?.toLocaleString()),
        distance: calcCoordinateDistance(galaxyInfo[kdId].coordinate || 0, props.data.kingdom.coordinate || 0).toString().padStart(2, '0') + ' (' + (galaxyInfo[kdId].coordinate || 0).toString().padStart(2, '0') + ')',
        status: galaxyInfo[kdId].status,
        networth: shown(kdId, "networth", known[kdId].kingdom.networth !== undefined ? Math.floor(known[kdId].kingdom.networth).toLocaleString() : undefined),
        offense: known[kdId].kingdom.military_estimate?.offense !== undefined
            ? shown(kdId, "military_estimate.offense", `≤ ${known[kdId].kingdom.military_estimate.offense.toLocaleString()}`) : undefined,
        defense: known[kdId].kingdom.military_estimate?.defense !== undefined
            ? shown(kdId, "military_estimate.defense", `≤ ${known[kdId].kingdom.military_estimate.defense.toLocaleString()}`) : undefined,
        // What is revealed about them and for how long, e.g. "military 3h, kingdom 40m".
        // A galaxymate who shares with you is known in full, with no timer.
        intel: (props.data.revealed?.revealed_galaxymates || []).includes(kdId) ? "shared with you"
            : Object.entries(props.data.revealed?.revealed?.[kdId] || {}).map(([what, until]) => `${what} ${timeLeft(until)}`).join(", "),
    });
    const galaxyCards = Object.keys(galaxyInfo).map((kdId) => {
        const facts = kingdomFacts(kdId);
        return (
            <div key={kdId} className="galaxy-card">
                <div className="galaxy-card-name">
                    <KingdomLink kdId={kdId} data={props.data}>{facts.name}</KingdomLink>
                </div>
                <dl className="galaxy-card-facts">
                    <div><dt>Race</dt><dd>{facts.race || "?"}</dd></div>
                    <div><dt>Stars</dt><dd>{facts.stars ?? "?"}</dd></div>
                    <div><dt>Networth</dt><dd>{facts.networth ?? "?"}</dd></div>
                    <div><dt>Distance</dt><dd>{facts.distance}</dd></div>
                    <div title="The most their army could be worth, with the largest bonuses and shields there can be">
                        <dt>Offense</dt><dd>{facts.offense ?? "?"}</dd>
                    </div>
                    <div title="The most their army could be worth, with the largest bonuses and shields there can be">
                        <dt>Defense</dt><dd>{facts.defense ?? "?"}</dd>
                    </div>
                    <div><dt>Status</dt><dd>{facts.status || "?"}</dd></div>
                    <div><dt>Intel</dt><dd>{facts.intel || "none"}</dd></div>
                </dl>
                <div className="galaxy-actions" data-tour="galaxy-actions">
                    {kingdomActions(kdId).map((action) => <IconButton key={action.label} {...action} />)}
                </div>
            </div>
        );
    });
    const NonexistentGalaxy = () => {
        setLoading(false);
        return <h3>This galaxy does not exist!</h3>
    }
    return (
        <>
        <div className="galaxy">
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
                ? <div className="galaxy-nav-container" data-tour="galaxy-nav">
                    <IconButton icon={BsChevronLeft} label="Previous galaxy" disabled />
                    <div className="box-tight galaxy-nav-input">
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
                    <IconButton icon={BsChevronRight} label="Next galaxy" disabled />
                </div>
                : <div className="galaxy-nav-container" data-tour="galaxy-nav">
                    <IconButton icon={BsChevronLeft} label="Previous galaxy" onClick={moveLeft} />
                    <div className="box-tight galaxy-nav-input">
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
                    <IconButton icon={BsChevronRight} label="Next galaxy" onClick={moveRight} />
                </div>
            }
            
            <ButtonGroup size="sm" className="galaxy-view-toggle" aria-label="Show kingdoms as">
                <Button variant={view === "table" ? "primary" : "outline-secondary"} aria-pressed={view === "table"} onClick={() => setView("table")}>Table</Button>
                <Button variant={view === "cards" ? "primary" : "outline-secondary"} aria-pressed={view === "cards"} onClick={() => setView("cards")}>Cards</Button>
            </ButtonGroup>
            {!(galaxiesArray[galaxyIndex] != undefined)
                ? <NonexistentGalaxy />
                : view === "cards"
                ? <div className="galaxy-cards" data-tour="galaxy-kingdoms">{galaxyCards}</div>
                : <div className="table-scroll" data-tour="galaxy-kingdoms"><Table hover className="galaxies-table" size="sm" >
                    <thead>
                        <tr>
                        <th>Kingdom</th>
                        <th>Race</th>
                        <th style={{textAlign: "right"}}>Stars</th>
                        {/* <th style={{textAlign: "right"}}>Networth</th>
                        <th style={{textAlign: "right"}}>Aggression</th> */}
                        <th style={{textAlign: "right"}}>Distance</th>
                        <th>Status</th>
                        <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {galaxyRows}
                    </tbody>
                </Table></div>
            }
            <HelpButton scrollTarget={"galaxy"}/>
        </div>
    </>
    );
}

export default Galaxy;