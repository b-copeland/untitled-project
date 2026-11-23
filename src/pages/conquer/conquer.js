import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./conquer.css";
import { useNavigate, useSearchParams } from "react-router-dom";
import { tradable } from "./intel.js";
import { KingdomLink, kingdomPath, targetPath } from "../../components/kingdomlink";
import { useFromHere } from "../../components/pagehead";
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { FilterMatchMode } from 'primereact/api';
import "primereact/resources/primereact.min.css";
import "primereact/resources/themes/bootstrap4-dark-blue/theme.css";     
import "primeicons/primeicons.css";
import 'bootstrap/dist/css/bootstrap.css';
import HelpButton from "../../components/helpbutton";
import { IconButton } from "../../components/iconbutton";
import { BsEye, BsBinoculars, BsRocketTakeoff, BsChatDots, BsPinAngle, BsPinAngleFill, BsClipboardData, BsGlobe2, BsCheckLg, BsHourglassSplit } from "react-icons/bs";
import { GiCrossedSwords } from "react-icons/gi";

import { ResultToasts } from "../../components/results";
import { withLastKnown, Known } from "../../components/lastknown";

// The action buttons in the tables here are icons, as on the Galaxy page: the word the button used to show is its tooltip.
const ICONS = {
    View: [BsEye, "View"], Attack: [GiCrossedSwords, "Attack"], Spy: [BsBinoculars, "Spy"], Missile: [BsRocketTakeoff, "Launch missiles"],
    Message: [BsChatDots, "Message"], Intel: [BsClipboardData, "Intel: share, buy or ask for it"], Galaxy: [BsGlobe2, "View galaxy"], Pin: [BsPinAngle, "Pin"],
    Unpin: [BsPinAngleFill, "Unpin"], Accept: [BsCheckLg, "Accept"], "Loading...": [BsHourglassSplit, "Loading..."],
};
function ActionButton({ children, disabled, onClick }) {
    const [icon, label] = ICONS[String(children).trim()] || [BsEye, String(children).trim()];
    return <IconButton icon={icon} label={label} onClick={onClick} disabled={disabled} active={String(children).trim() === "Unpin"} />;
}



function ConquerContent(props) {
    // The tab goes in the address (?tab=pinned), so a page opened from here links back to the same tab (#222).
    const [params, setParams] = useSearchParams();
    const tab = params.get("tab") === "pinned" ? "pinned" : "revealed";
    const openTab = (key) => setParams(key === "revealed" ? {} : { tab: key }, { replace: true });
    return (
    <>
      <Tabs
        id="conquer-tabs"
        data-tour="conquer-tabs"
        activeKey={tab}
        variant="tabs"
        onSelect={openTab}
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
    const navigate = useNavigate();
    const fromHere = useFromHere();
    // The kingdom, the planners and the galaxy are pages of their own, opened on this row; they link back here.
    const go = (path) => navigate(path, { state: fromHere });
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
        return rowData.stars !== null
            ? <Known ended={rowData.starsEnded} gameConfig={props.data.state?.game_config}>{rowData.stars.toLocaleString()}</Known>
            : null
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
            "kdId": kdId,
            "remaining": getRemainingSpans(kdId, props.revealed.revealed),
            "kingdom": props.kingdoms[kdId] || "",
            "galaxy": (
                empireName !== undefined
                ? (props.galaxies_inverted[kdId] || "") + ' (' + empireName + ')'
                : props.galaxies_inverted[kdId] || ""
            ),
            // "empire": props.empires[props.empires_inverted?.empires_inverted[kdId]]?.name || "",
            // Live, or what ended intel last showed (components/lastknown.js).
            "stars": withLastKnown(maxKdInfo[kdId]).kingdom.stars || null,
            "starsEnded": withLastKnown(maxKdInfo[kdId]).endedOf("stars"),
            "coordinate_distance": calcCoordinateDistance(maxKdInfo[kdId]?.coordinate || 0, props.data.kingdom?.coordinate || 0).toString().padStart(2, '0') + ' (' + (maxKdInfo[kdId]?.coordinate || 0).toString().padStart(2, '0') + ')',
            "actions": <>
                <ActionButton onClick={() => go(kingdomPath(kdId))}>
                    View
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/attack", kdId))}>
                    Attack
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/spy", kdId))}>
                    Spy
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/launchmissiles", kdId))}>
                    Missile
                </ActionButton>
                <ActionButton onClick={() => go(`/message?to=${kdId}`)}>
                    Message
                </ActionButton>
                {tradable(props.data, kdId) ? <ActionButton onClick={() => go(kingdomPath(kdId, "intel"))}>
                    Intel
                </ActionButton> : null}
                <ActionButton onClick={() => go("/galaxy?galaxy=" + encodeURIComponent(props.galaxies_inverted[kdId] || ""))}>
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
                scrollable
                
            >
                <Column field="kingdom" header="Kingdom" filter filterPlaceholder="Search" frozen showFilterMenu={false} style={{ width: "15%" }}
                    body={(row) => <KingdomLink kdId={row.kdId} data={props.data}>{row.kingdom}</KingdomLink>}/>
                <Column field="remaining" header="Remaining" style={{ width: "15%" }}/>
                <Column field="galaxy" header="Galaxy" sortable filter filterPlaceholder="Search" showFilterMenu={false} style={{ width: "15%" }}/>
                {/* <Column field="empire" header="Empire" sortable showFilterMenu={false} filter style={{ width: '10%' }}/> */}
                <Column field="stars" header="Stars" sortable /*filter*/ dataType="numeric" body={formatStars} style={{ width: "15%" , textAlign:"right"}}/>
                {/* <Column field="networth" header="Networth" sortable filter body={formatScore} style={{ width: '10%' }}/> */}
                <Column field="coordinate_distance" header="Distance" sortable /*filter*/ style={{ width: "10%" , textAlign:"right"}}/>
                <Column field="actions" header="Actions" style={{ minWidth: '110px', width: "30%" }}/>
            </DataTable>
            <div className="table-scroll">
            <Table className="revealed-galaxy-table" hover>
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
        </div>
    )
}

function Pinned(props) {
    const [maxKdInfo, setMaxKdInfo] = useState({});
    const navigate = useNavigate();
    const fromHere = useFromHere();
    // The kingdom, the planners and the galaxy are pages of their own, opened on this row; they link back here.
    const go = (path) => navigate(path, { state: fromHere });

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
    // A pinned kingdom's stars and networth: live, or what ended intel last showed (components/lastknown.js).
    const shownKnown = (kdId, field) => {
        const { kingdom, endedOf } = withLastKnown(maxKdInfo[kdId]);
        return kingdom[field] !== undefined
            ? <Known ended={endedOf(field)} gameConfig={props.data?.state?.game_config}>{Math.floor(kingdom[field]).toLocaleString()}</Known>
            : "";
    };
    const revealedRows = props.pinned.map((kdId) => {
        const empireName = props.empires[props.empires_inverted?.empires_inverted[kdId]]?.name;
        const galaxyEmpire = (
            empireName !== undefined
            ? (props.galaxies_inverted[kdId] || "") + ' (' + empireName + ')'
            : props.galaxies_inverted[kdId] || ""
        )
        return <tr key={kdId}>
            <td>{getRemainingSpans(kdId, props.revealed.revealed)}</td>
            <td><KingdomLink kdId={kdId} data={props.data}>{props.kingdoms[kdId] || ""}</KingdomLink></td>
            <td>{galaxyEmpire}</td>
            <td>{shownKnown(kdId, "stars")}</td>
            <td>{shownKnown(kdId, "networth")}</td>
            <td>
                <ActionButton onClick={() => go(kingdomPath(kdId))}>
                    View
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/attack", kdId))}>
                    Attack
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/spy", kdId))}>
                    Spy
                </ActionButton>
                <ActionButton onClick={() => go(targetPath("/launchmissiles", kdId))}>
                    Missile
                </ActionButton>
                <ActionButton onClick={() => go(`/message?to=${kdId}`)}>
                    Message
                </ActionButton>
                {tradable(props.data, kdId) ? <ActionButton onClick={() => go(kingdomPath(kdId, "intel"))}>
                    Intel
                </ActionButton> : null}
                <ActionButton onClick={() => go("/galaxy?galaxy=" + encodeURIComponent(props.galaxies_inverted[kdId] || ""))}>
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
            <div className="table-scroll">
            <Table className="table-small pinned-table" hover size="sm">
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
        </div>
    )
}

export default ConquerContent;