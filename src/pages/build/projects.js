import { displayDuration, displayPercent } from "../../format";
import React, { useEffect, useRef, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import { AmountInput, SubmitButton, useSliders } from "../../components/forms";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import OverlayTrigger from 'react-bootstrap/OverlayTrigger';
import Popover from 'react-bootstrap/Popover';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./projects.css";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { inOrder, entriesInOrder } from "../../order";
import { useProjectsFollowKingdom } from "../../data/gameData";

function ProjectsContent(props) {
    const kdInfo = props.data.kingdom;
    const engineersInfo = props.data.engineers;
    const projectsInfo = props.data.projects;
    useProjectsFollowKingdom(kdInfo, props.updateData);
    return (
    <>
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="train"
          variant="tabs"
        >
          <Tab eventKey="train" title="Train">
            <Train kdInfo={kdInfo} engineersInfo={engineersInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="assign" title="Assign">
            <Assign state={props.data.state} kdInfo={kdInfo} engineersInfo={engineersInfo} projectsInfo={projectsInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="allocate" title="Allocate">
            <Allocate state={props.data.state} kdInfo={kdInfo} engineersInfo={engineersInfo} projectsInfo={projectsInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
        </Tabs>
        <HelpButton scrollTarget={"projects"}/>
    </>
    )
}

function Train(props) {
    const [engineersInput, setEngineersInput] = useState("");
    const [engineersResult, setEngineersResult] = useState([]);

    const handleEngineersInput = (e) => {
        setEngineersInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (engineersInput > 0) {
            let opts = {
                'engineersInput': engineersInput,
            };
            const updateFunc = () => authFetch('api/engineers', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setEngineersResult(engineersResult.concat(r)))
            props.updateData(['engineers', 'kingdom'], [updateFunc]);
            setEngineersInput('');
        }
    }
    if (Object.keys(props.engineersInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const calcTrainCosts = (input) => parseInt(input || 0) * props.engineersInfo.engineers_price;
    const trainCosts = calcTrainCosts(engineersInput);
    const engineerPrice = props.engineersInfo.engineers_price || 0;
    const maxEngineers = Math.min(props.engineersInfo.current_available_engineers || 0,
        engineerPrice > 0 ? Math.floor((props.kdInfo.money || 0) / engineerPrice) : Infinity);
    return (
        <div className="engineers">
            <ResultToasts title="Structures Results" results={engineersResult} setResults={setEngineersResult} />
            <div className="text-box text-box-stats engineers-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Time</span>
                    <span className="text-box-item-value">12h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Cost</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_price?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Workshop Capacity</span>
                    <span className="text-box-item-value">
                        {props.engineersInfo.current_workshop_capacity?.toLocaleString()} / {props.engineersInfo.max_workshop_capacity?.toLocaleString()} ({displayPercent(props.engineersInfo.current_workshop_capacity / props.engineersInfo.max_workshop_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.engineers_building?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.max_available_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_available_engineers?.toLocaleString()}</span>
                </div>
                <div className="summary-form">
                    <div className="amount-field">
                        <label htmlFor="engineers-input">New engineers</label>
                        <AmountInput name="engineers" id="engineers-input" label="New engineers" value={engineersInput}
                            onChange={handleEngineersInput} max={maxEngineers} />
                    </div>
                    {props.loading.engineers
                    ? <Button className="engineers-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="engineers-button" variant="primary" type="submit" onClick={onSubmitClick}>
                        Train
                    </Button>
                    }
                    {
                        trainCosts !== 0
                        ? <span className="text-muted">Engineers Cost: {trainCosts.toLocaleString()}</span>
                        : null
                    }
                </div>
            </div>
        </div>
    )
}

/**
 * The projects this kingdom can see, grouped by category in the server's order: every project but another race's.
 * Each entry is {key, name, desc, oneTime, locked (why, or undefined), completed}.
 */
export function projectRows(state, kdInfo, projectsInfo) {
    const projects = state?.projects || {};
    const categories = state?.project_categories || {};
    const completed = kdInfo.completed_projects || [];
    const groups = {};
    for (const [key, project] of entriesInOrder(projects, state?.order?.projects)) {
        if (project.race && project.race !== kdInfo.race) {
            continue;
        }
        const category = project.category || "other";
        groups[category] = groups[category] || [];
        groups[category].push({
            key,
            name: project.name,
            desc: project.desc,
            oneTime: project.max_bonus === undefined,
            locked: projectsInfo.locked?.[key],
            completed: completed.indexOf(key) >= 0,
        });
    }
    const order = inOrder(Object.keys(categories), state?.order?.project_categories);
    return Object.keys(groups)
        .sort((a, b) => (order.indexOf(a) < 0 ? 99 : order.indexOf(a)) - (order.indexOf(b) < 0 ? 99 : order.indexOf(b)))
        .map((category) => ({ category, title: categories[category] || category, rows: groups[category] }));
}

/**
 * The page's two sections: continuous projects (a bonus that grows with points) in one table, then one-time projects
 * (done once, then they unlock something or give a fixed bonus) in one table per category. Empty sections are left out.
 */
export function projectSections(state, kdInfo, projectsInfo) {
    const groups = projectRows(state, kdInfo, projectsInfo);
    const continuous = groups.flatMap((group) => group.rows.filter((row) => !row.oneTime));
    const oneTime = groups
        .map((group) => ({ ...group, rows: group.rows.filter((row) => row.oneTime) }))
        .filter((group) => group.rows.length > 0);
    return [
        { key: "continuous", title: "Continuous Projects", valueHeader: "Bonus / Max",
          note: "The bonus grows with points, up to its maximum. The points needed grow with your stars.",
          groups: continuous.length > 0 ? [{ category: "continuous", title: null, rows: continuous }] : [] },
        { key: "one-time", title: "One-Time Projects", valueHeader: "Progress",
          note: "Done once the points are reached, and then permanent.",
          groups: oneTime },
    ].filter((section) => section.groups.length > 0);
}

function blankValues(state) {
    return Object.fromEntries(Object.keys(state?.projects || {}).map((key) => [key, ""]));
}

/**
 * How long until the project reaches its max points at the engineers on it now (``seconds`` from the server's
 * ``seconds_left``: 0 once there, null with nobody on it). A continuous project's max points grow with stars, so its
 * time is marked as an estimate. Nothing with nobody on it, for a locked or completed project, or before the server
 * sends it.
 */
export function timeLeft(row, seconds) {
    // With nobody on it the Assigned column already says so.
    if (seconds === undefined || seconds === null || row.locked || (row.oneTime && row.completed)) return null;
    if (seconds === 0) return row.oneTime ? null : "At its maximum";
    return row.oneTime ? `Done in ${displayDuration(seconds)}` : `Maximum in about ${displayDuration(seconds)}`;
}

/** Points earned / needed, and what they are worth: the bonus for a continuous project, the progress for a one-time one. */
function projectCells(row, kdInfo, engineersInfo, projectsInfo) {
    const points = projectsInfo.points?.[row.key] ?? kdInfo.projects_points?.[row.key] ?? 0;
    const maxPoints = projectsInfo.max_points?.[row.key] ?? kdInfo.projects_max_points?.[row.key] ?? 0;
    const assigned = kdInfo.projects_assigned?.[row.key] || 0;
    return {
        timeLeft: timeLeft(row, projectsInfo.seconds_left?.[row.key]),
        assigned: `${assigned.toLocaleString()} (${displayPercent(assigned / (engineersInfo.current_engineers || 0))})`,
        points: `${Math.floor(points).toLocaleString()} / ${Math.floor(maxPoints).toLocaleString()}`,
        value: row.oneTime
            ? (row.completed ? "Completed" : displayPercent(maxPoints > 0 ? Math.min(points / maxPoints, 1) : 0))
            : `${displayPercent(projectsInfo.current_bonuses?.[row.key] || 0)} / ${displayPercent(projectsInfo.max_bonuses?.[row.key] || 0)}`,
    };
}

/**
 * The project's name and what it does. Wide screens show the description under the name; narrow ones hide it (it made
 * every row tall) and show an (i) button that opens it in a popover instead. Which one shows is up to projects.css.
 */
function ProjectName({ row }) {
    const about = (
        <Popover id={`${row.key}-about`}>
            <Popover.Header as="h3">{row.name}</Popover.Header>
            <Popover.Body>{row.desc}</Popover.Body>
        </Popover>
    );
    return (
        <div className="project-name">
            <span className="project-name-line">
                {row.name}
                <OverlayTrigger trigger="click" placement="auto" rootClose overlay={about}>
                    <button type="button" className="project-info-button" aria-label={`About ${row.name}`}>i</button>
                </OverlayTrigger>
            </span>
            <small className="project-desc">{row.desc}</small>
        </div>
    );
}

/**
 * Each section of ``projectSections`` under its heading, its groups drawn by ``ProjectTables``. ``footer`` (the
 * form's buttons) is repeated after each table, so a long page never needs scrolling back to send.
 */
function ProjectSections({ state, kdInfo, projectsInfo, footer, ...tableProps }) {
    return projectSections(state, kdInfo, projectsInfo).map((section) => (
        <div className="projects-section" key={section.key}>
            <h4 className="projects-section-title">{section.title}</h4>
            <small className="projects-section-note">{section.note}</small>
            <ProjectTables groups={section.groups} valueHeader={section.valueHeader} kdInfo={kdInfo}
                projectsInfo={projectsInfo} footer={footer} {...tableProps} />
        </div>
    ));
}

/** One table per category. ``inputs(row)`` gives the cells after the shared ones; ``inputHeaders`` their headers. */
function ProjectTables({ groups, valueHeader, kdInfo, engineersInfo, projectsInfo, inputHeaders, inputs, footer }) {
    return groups.map(({ category, title, rows }) => {
        const blocked = (row) => Boolean(row.locked) || (row.oneTime && row.completed);
        const columns = [
            { header: "Project", align: "left", cell: (row) => <ProjectName row={row} /> },
            // A locked project says what unlocks it in the Assigned column only; its points still show.
            { header: "Assigned", className: "assigned-col",
              cell: (row) => (row.locked
                  ? <span className="project-locked">{row.locked}</span>
                  : projectCells(row, kdInfo, engineersInfo, projectsInfo).assigned) },
            { header: "Points", cell: (row) => {
                const cells = projectCells(row, kdInfo, engineersInfo, projectsInfo);
                return <>{cells.points}{cells.timeLeft ? <small className="project-time-left">{cells.timeLeft}</small> : null}</>;
            } },
            { header: valueHeader, cell:(row) => projectCells(row, kdInfo, engineersInfo, projectsInfo).value },
            ...inputHeaders.map((header, index) => ({ header, phoneRow: index === inputHeaders.length - 1, cell: (row) => inputs(row, blocked(row))[index] })),
        ];
        return (
            <div className="projects-category" key={category}>
                {title ? <h5 className="projects-category-title">{title}</h5> : null}
                <GameTable className="game-table projects-table" columns={columns} rows={rows}
                    rowClassName={(row) => (row.oneTime && row.completed ? "disabled-table-row" : undefined)} />
                {footer}
            </div>
        );
    });
}

/**
 * Engineers on projects, set directly: each project's slider starts at what it has now and runs to all your engineers,
 * less what the others are set to. Update sends every project's number (the server's "assign" replaces them all), so
 * a project left alone keeps what it has. Moving a slider to 0 takes its engineers off.
 */
function Assign(props) {
    const current = props.kdInfo.projects_assigned || {};
    const sliders = useSliders(current);
    const [assignResult, setAssignResult] = useState([]);

    if (Object.keys(props.engineersInfo).length === 0 || Object.keys(props.kdInfo).length === 0
        || Object.keys(props.projectsInfo).length === 0) {
        return null;
    }
    const keys = Object.keys(blankValues(props.state));
    const engineers = Math.floor(props.engineersInfo.current_engineers || 0);
    const totalWanted = keys.reduce((sum, key) => sum + sliders.value(key), 0);
    const blocked = totalWanted > engineers ? "More engineers than you have"
        : sliders.changed ? null : "Move a slider to change a project's engineers";

    const onUpdate = () => {
        const assign = Object.fromEntries(keys.map((key) => [key, sliders.value(key)]));
        const updateFunc = () => authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify({ assign }),
        }).then(r => r.json()).then(r => setAssignResult((previous) => previous.concat(r)));
        props.updateData(['projects', 'kingdom'], [updateFunc]);
        sliders.reset();
    };
    const inputs = (row, isBlocked) => [
        <AmountInput name={row.key} id={`${row.key}-assign-input`} label={`Engineers on ${row.name}`}
            value={String(sliders.value(row.key))}
            onChange={sliders.onChange} disabled={isBlocked && !current[row.key]}
            max={Math.max(engineers - (totalWanted - sliders.value(row.key)), 0)} soloMax={engineers} />,
    ];
    const actions = (
        <div className="form-actions">
            <span className={totalWanted > engineers ? "text-danger" : "text-muted"}>
                {(engineers - totalWanted).toLocaleString()} of {engineers.toLocaleString()} engineers unassigned
            </span>
            {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
            <SubmitButton loading={props.loading.projects} blocked={blocked} onClick={onUpdate}>Update</SubmitButton>
        </div>
    );
    return (
        <div className="projects">
            <ResultToasts title="Projects Results" results={assignResult} setResults={setAssignResult} />
            <div className="text-box text-box-stats projects-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Total Engineers</span>
                    <span className="text-box-item-value">{engineers.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Unassigned now</span>
                    <span className="text-box-item-value">{Math.floor(props.projectsInfo.available_engineers || 0).toLocaleString()}</span>
                </div>
            </div>
            <ProjectSections state={props.state} kdInfo={props.kdInfo} engineersInfo={props.engineersInfo} projectsInfo={props.projectsInfo}
                inputHeaders={["Engineers"]} inputs={inputs} footer={actions} />
        </div>
    )
}

export function Allocate(props) {
    const keys = Object.keys(blankValues(props.state));
    const sliders = useSliders(Object.fromEntries(keys.map((key) => [key, (props.kdInfo.projects_target?.[key] || 0) * 100])));
    const [assignResult, setAssignResult] = useState([]);

    const send = (opts) => {
        const updateFunc = () => authFetch('api/projects/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const onSubmitClick = () => { send({ "targets": sliders.body(keys) }); sliders.reset(); };
    const handleEnabledChange = (e) => send({ 'enabled': e.target.checked });

    if (Object.keys(props.engineersInfo).length === 0 || Object.keys(props.kdInfo).length === 0
        || Object.keys(props.projectsInfo).length === 0) {
        return null;
    }
    const total = sliders.total(keys);
    const blocked = total > 100 ? "The shares add up to more than 100%"
        : sliders.changed ? null : "Move a slider to change a project's share";

    const inputs = (row, isBlocked) => [
        displayPercent(props.kdInfo.projects_target?.[row.key] || 0),
        <AmountInput name={row.key} id={`${row.key}-allocate-input`} label={`Allocate to ${row.name}`} value={String(sliders.value(row.key))}
            onChange={sliders.onChange} suffix="%" max={isBlocked ? 0 : Math.max(100 - (total - sliders.value(row.key)), 0)}
            soloMax={isBlocked ? 0 : 100} disabled={isBlocked} />,
    ];
    return (
        <div className="projects">
            <ResultToasts title="Projects Results" results={assignResult} setResults={setAssignResult} />
            <p className="page-note">Choose the target allocation of assigned engineers that you would like the auto-spender to assign towards</p>
            <Form>
                <Form.Check
                    type="switch"
                    id="enable-auto-projects-switch"
                    label="Enable Auto Assign Engineers?"
                    checked={props.kdInfo.auto_assign_projects}
                    onChange={handleEnabledChange}
                    disabled={props.loading.kingdom}
                />
            </Form>
            <ProjectSections state={props.state} kdInfo={props.kdInfo} engineersInfo={props.engineersInfo} projectsInfo={props.projectsInfo}
                inputHeaders={["Current Allocation", "New Allocation"]} inputs={inputs} footer={
                    <div className="form-actions projects-buttons">
                        <span className={total > 100 ? "text-danger" : "text-muted"}>{total}% of 100%</span>
                        {sliders.changed ? <Button variant="link" size="sm" onClick={sliders.reset}>Undo changes</Button> : null}
                        <SubmitButton loading={props.loading.kingdom} blocked={blocked} onClick={onSubmitClick}>Update</SubmitButton>
                    </div>} />
        </div>
    )
}

export default ProjectsContent;
