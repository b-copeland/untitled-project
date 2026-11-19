import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Modal from 'react-bootstrap/Modal';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./conquer.css";
import Galaxy from "../galaxy.js";
import Attack from "./attack.js";
import Spy from "./spy.js";
import LaunchMissiles from "./launchmissiles.js";
import { KingdomIntel } from "./intel.js";
import Message from "../message.js";
import Kingdom from "../kingdominfo.js";
import Header from "../../components/header";
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { FilterMatchMode } from 'primereact/api';
import "primereact/resources/primereact.min.css";
import "primereact/resources/themes/bootstrap4-dark-blue/theme.css";     
import "primeicons/primeicons.css";
import 'bootstrap/dist/css/bootstrap.css';
import HelpButton from "../../components/helpbutton";
import { IconButton } from "../../components/iconbutton";
import { BsEye, BsBinoculars, BsRocketTakeoff, BsChatDots, BsPinAngle, BsPinAngleFill, BsShare, BsGlobe2, BsCheckLg, BsHourglassSplit } from "react-icons/bs";
import { GiCrossedSwords } from "react-icons/gi";

import { ResultToasts } from "../../components/results";

// The action buttons in the tables here are icons, as on the Galaxy page: the word the button used to show is its tooltip.
const ICONS = {
    View: [BsEye, "View"], Attack: [GiCrossedSwords, "Attack"], Spy: [BsBinoculars, "Spy"], Missile: [BsRocketTakeoff, "Launch missiles"],
    Message: [BsChatDots, "Message"], Intel: [BsShare, "Intel: share, buy or ask for it"], Galaxy: [BsGlobe2, "View galaxy"], Pin: [BsPinAngle, "Pin"],
    Unpin: [BsPinAngleFill, "Unpin"], Accept: [BsCheckLg, "Accept"], "Loading...": [BsHourglassSplit, "Loading..."],
};
function ActionButton({ children, disabled, onClick }) {
    const [icon, label] = ICONS[String(children).trim()] || [BsEye, String(children).trim()];
    return <IconButton icon={icon} label={label} onClick={onClick} disabled={disabled} active={String(children).trim() === "Unpin"} />;
}



function ConquerContent(props) {
    const [key, setKey] = useState('kingdom');

    const handleNotifsSelect = (eventKey) => {
        setKey(eventKey);
    }
    return (
    <>
        <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="revealed"
        justify
        fill
        variant="tabs"
        onSelect={(k) => handleNotifsSelect(k)}
      >
        <Tab eventKey="revealed" title="Revealed">
          <Revealed
            revealed={props.data.revealed}
            kingdoms={props.data.kingdoms}
            galaxies_inverted={props.data.galaxies_inverted}
            empires={props.data.empires}
            empires_inverted={props.data.empires_inverted}
            pinned={props.data.pinned}
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
            />
        </Tab>
        <Tab eventKey="pinned" title="Pinned">
          <Pinned
            revealed={props.data.revealed}
            kingdoms={props.data.kingdoms}
            galaxies_inverted={props.data.galaxies_inverted}
            empires={props.data.empires}
            empires_inverted={props.data.empires_inverted}
            pinned={props.data.pinned}
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"conquer"}/>
    </>
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

function Revealed(props) {
    const [maxKdInfo, setMaxKdInfo] = useState({});
    const [showView, setShowView] = useState(false);
    const [showAttack, setShowAttack] = useState(false);
    const [showSpy, setShowSpy] = useState(false);
    const [showMissile, setShowMissile] = useState(false);
    const [showMessage, setShowMessage] = useState(false);
    const [showIntel, setShowIntel] = useState(false);
    const [showGalaxy, setShowGalaxy] = useState(false);
    const [galaxyToShow, setGalaxyToShow] = useState('');
    const [kdToShow, setKdToShow] = useState();
    const [filters, setFilters] = useState({
        remaining: { value: null, matchMode: FilterMatchMode.CONTAINS },
        kingdom: { value: null, matchMode: FilterMatchMode.CONTAINS },
        galaxy: { value: null, matchMode: FilterMatchMode.CONTAINS },
        empire: { value: null, matchMode: FilterMatchMode.CONTAINS },
        stars: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        // networth: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        coordinate_distance: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });
    const [results, setResults] = useState([]);

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
        const updateFunc = () => authFetch('api/revealrandomgalaxy').then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['revealed', 'kingdom'], [updateFunc])
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
    const formatStars = (rowData) => {
        return rowData.stars !== null ? rowData.stars.toLocaleString() : null
    }
    const formatScore = (rowData) => {
        return rowData.networth !== null ? rowData.networth.toLocaleString() : null
    }
    
    const getRemainingSpans = (kdId, revealed) => {
        const remainingSpans = Object.keys(revealed[kdId] || {}).map((category) =>
            <div key={kdId.toString() + '_' + category} className="row remaining-timer">
                <span className="remaining-time-title">{category}</span>
                <span className="remaining-time-value">{getTimeString(revealed[kdId][category])}</span>
                <br />
            </div>
        )
        return remainingSpans;
    }
    const calcCoordinateDistance = (coord_a, coord_b) => {

        const direct_distance = Math.abs(coord_a - coord_b)
        const indirect_distance_1 = (coord_a) + (99 - coord_b)
        const indirect_distance_2 = (coord_b) + (99 - coord_a)
        return Math.min(direct_distance, indirect_distance_1, indirect_distance_2);
    }
    const revealedPrimeRows = Object.keys(props.revealed.revealed).map((kdId) => {
        const empireName = props.empires[props.empires_inverted?.empires_inverted[kdId]]?.name;
        return {
            "remaining": getRemainingSpans(kdId, props.revealed.revealed),
            "kingdom": props.kingdoms[kdId] || "",
            "galaxy": (
                empireName !== undefined
                ? (props.galaxies_inverted[kdId] || "") + ' (' + empireName + ')'
                : props.galaxies_inverted[kdId] || ""
            ),
            // "empire": props.empires[props.empires_inverted?.empires_inverted[kdId]]?.name || "",
            "stars": maxKdInfo[kdId]?.stars || null,
            "coordinate_distance": calcCoordinateDistance(maxKdInfo[kdId]?.coordinate || 0, props.data.kingdom?.coordinate || 0).toString().padStart(2, '0') + ' (' + (maxKdInfo[kdId]?.coordinate || 0).toString().padStart(2, '0') + ')',
            "actions": <>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowView(true)}}>
                    View
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowAttack(true)}}>
                    Attack
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowSpy(true)}}>
                    Spy
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowMissile(true)}}>
                    Missile
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); {setKdToShow(kdId); setShowMessage(true)}}}>
                    Message
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowIntel(true)}}>
                    Intel
                </ActionButton>
                <ActionButton onClick={() => {setGalaxyToShow(props.galaxies_inverted[kdId] || ""); setShowGalaxy(true);}}>
                    Galaxy
                </ActionButton>
                {
                    props.loading.pinned
                    ? <ActionButton name={kdId} disabled>
                        Loading...
                    </ActionButton>
                    : props.pinned.indexOf(kdId) >= 0
                    ? <ActionButton name={kdId} onClick={onSubmitUnpin}>
                        Unpin
                    </ActionButton>
                    : <ActionButton name={kdId} onClick={onSubmitPin}>
                        Pin
                    </ActionButton>
                }
            </>
        }
    });
    const revealedGalaxyRows = Object.keys(props.revealed.galaxies).map((galaxyId) =>
        <tr key={galaxyId}>
            <td>{getTimeString(props.revealed.galaxies[galaxyId])}</td>
            <td>{galaxyId || ""}</td>
            <td>{props.empires[props.empires_inverted?.galaxy_empires[galaxyId]]?.name || ""}</td>
        </tr>
    );
    return (
        <div className="revealed">
            <ResultToasts title="Reveal Results" results={results} setResults={setResults} />
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
                    <Kingdom data={{"kingdom": maxKdInfo[kdToShow], "kingdoms": props.kingdoms, "galaxies_inverted": props.galaxies_inverted, "shields": props.data.shields, "state": props.data.state, "kdId": kdToShow}}/>
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
                show={showIntel}
                onHide={() => setShowIntel(false)}
                animation={false}
                dialogClassName="intel-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>Intel</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <KingdomIntel data={props.data} loading={props.loading} updateData={props.updateData} target={kdToShow}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowIntel(false)}>
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
                    <Galaxy data={props.data} loading={props.loading} updateData={props.updateData} initialGalaxyId={galaxyToShow}/>
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
            <DataTable
                className="box-loose revealed-table"
                value={revealedPrimeRows}
                paginator
                size="small"
                // columnResizeMode="expand"
                rows={10}
                rowsPerPageOptions={[5, 10, 25, 50]}
                sortMode="multiple"
                removableSort
                filters={filters}
                filterDisplay="row"
                // style={{ minWidth: '100%'}}
                header={"Revealed Kingdoms"}
                showGridlines={true}
                scrollable
                
            >
                <Column field="kingdom" header="Kingdom" filter frozen showFilterMenu={false} style={{ width: "15%" }}/>
                <Column field="remaining" header="Remaining" style={{ width: "15%" }}/>
                <Column field="galaxy" header="Galaxy" sortable filter showFilterMenu={false} style={{ width: "15%" }}/>
                {/* <Column field="empire" header="Empire" sortable showFilterMenu={false} filter style={{ width: '10%' }}/> */}
                <Column field="stars" header="Stars" sortable /*filter*/ dataType="numeric" body={formatStars} style={{ width: "15%" , textAlign:"right"}}/>
                {/* <Column field="networth" header="Networth" sortable filter body={formatScore} style={{ width: '10%' }}/> */}
                <Column field="coordinate_distance" header="Distance" sortable /*filter*/ style={{ width: "10%" , textAlign:"right"}}/>
                <Column field="actions" header="Actions" style={{ minWidth: '110px', width: "30%" }}/>
            </DataTable>
            <Table className="box-loose revealed-galaxy-table" striped bordered hover>
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

function Pinned(props) {
    const [maxKdInfo, setMaxKdInfo] = useState({});
    const [showView, setShowView] = useState(false);
    const [showAttack, setShowAttack] = useState(false);
    const [showSpy, setShowSpy] = useState(false);
    const [showMissile, setShowMissile] = useState(false);
    const [showMessage, setShowMessage] = useState(false);
    const [showGalaxy, setShowGalaxy] = useState(false);
    const [galaxyToShow, setGalaxyToShow] = useState('');
    const [kdToShow, setKdToShow] = useState();

    useEffect(() => {
        const fetchData = async () => {
            if (props.pinned.length > 0) {
                const opts = {"kingdoms": props.pinned}
                await authFetch("api/kingdomsinfo", {
                    method: "POST",
                    body: JSON.stringify(opts)
                }).then(r => r.json()).then(r => setMaxKdInfo(r));
            };
        }
        fetchData();
    }, [props.pinned])
    // if (props.loading.pinned) {
    //     return <h2>Loading...</h2>
    // }

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
    
    const getRemainingSpans = (kdId, revealed) => {
        const remainingSpans = Object.keys(revealed[kdId] || {}).map((category) =>
            <div key={kdId.toString() + '_' + category} className="row remaining-timer">
                <span className="remaining-time-title">{category}</span>
                <span className="remaining-time-value">{getTimeString(revealed[kdId][category])}</span>
                <br />
            </div>
        )
        return remainingSpans;
    }
    const revealedRows = props.pinned.map((kdId) => {
        const empireName = props.empires[props.empires_inverted?.empires_inverted[kdId]]?.name;
        const galaxyEmpire = (
            empireName !== undefined
            ? (props.galaxies_inverted[kdId] || "") + ' (' + empireName + ')'
            : props.galaxies_inverted[kdId] || ""
        )
        return <tr key={kdId}>
            <td>{getRemainingSpans(kdId, props.revealed.revealed)}</td>
            <td>{props.kingdoms[kdId] || ""}</td>
            <td>{galaxyEmpire}</td>
            <td>{maxKdInfo[kdId]?.stars || ""}</td>
            <td>{maxKdInfo[kdId]?.networth || ""}</td>
            <td>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowView(true)}}>
                    View
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowAttack(true)}}>
                    Attack
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowSpy(true)}}>
                    Spy
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowMissile(true)}}>
                    Missile
                </ActionButton>
                <ActionButton onClick={() => {setKdToShow(kdId); setShowMessage(true)}}>
                    Message
                </ActionButton>
                <ActionButton onClick={() => {setGalaxyToShow(props.galaxies_inverted[kdId] || ""); setShowGalaxy(true);}}>
                    Galaxy
                </ActionButton>
                {
                    props.loading.pinned
                    ? <ActionButton name={kdId} disabled>
                        Loading...
                    </ActionButton>
                    : props.pinned.indexOf(kdId) >= 0
                    ? <ActionButton name={kdId} onClick={onSubmitUnpin}>
                        Unpin
                    </ActionButton>
                    : <ActionButton name={kdId} onClick={onSubmitPin}>
                        Pin
                    </ActionButton>
                }
            </td>
        </tr>
    }
    );
    return (
        <div className="revealed">
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
                    <Kingdom data={{"kingdom": maxKdInfo[kdToShow], "kingdoms": props.kingdoms, "galaxies_inverted": props.galaxies_inverted, "shields": props.data.shields, "state": props.data.state, "kdId": kdToShow}}/>
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
                show={showGalaxy}
                onHide={() => setShowGalaxy(false)}
                animation={false}
                dialogClassName="galaxy-modal"
            >
                <Modal.Header closeButton>
                    <Modal.Title>View Galaxy</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Galaxy data={props.data} loading={props.loading} updateData={props.updateData} initialGalaxyId={galaxyToShow}/>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowGalaxy(false)}>
                    Close
                    </Button>
                </Modal.Footer>
            </Modal>
            <Table className="table-small pinned-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th>Remaining</th>
                        <th>Kingdom</th>
                        <th>Galaxy</th>
                        <th>Stars</th>
                        <th>Networth</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {revealedRows}
                </tbody>
            </Table>
        </div>
    )
}

export default ConquerContent;