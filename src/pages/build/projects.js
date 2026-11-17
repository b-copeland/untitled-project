import { displayPercent } from "../../format";
import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import { AmountInput } from "../../components/forms";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./projects.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { inOrder, entriesInOrder } from "../../order";

function ProjectsContent(props) {
    const kdInfo = props.data.kingdom;
    const engineersInfo = props.data.engineers;
    const projectsInfo = props.data.projects;
    return (
    <>
        <Header data={props.data} />
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="train"
          justify
          fill
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
            <div className="text-box engineers-box">
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
                    ? <h3>Engineers Cost: {trainCosts.toLocaleString()}</h3>
                    : null
                }
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

/** Points earned / needed, and what they are worth: the bonus for a continuous project, the progress for a one-time one. */
function projectCells(row, kdInfo, engineersInfo, projectsInfo) {
    const points = projectsInfo.points?.[row.key] ?? kdInfo.projects_points?.[row.key] ?? 0;
    const maxPoints = projectsInfo.max_points?.[row.key] ?? kdInfo.projects_max_points?.[row.key] ?? 0;
    const assigned = kdInfo.projects_assigned?.[row.key] || 0;
    return {
        assigned: `${assigned.toLocaleString()} (${displayPercent(assigned / (engineersInfo.current_engineers || 0))})`,
        points: `${Math.floor(points).toLocaleString()} / ${Math.floor(maxPoints).toLocaleString()}`,
        value: row.oneTime
            ? (row.completed ? "Completed" : displayPercent(maxPoints > 0 ? Math.min(points / maxPoints, 1) : 0))
            : `${displayPercent(projectsInfo.current_bonuses?.[row.key] || 0)} / ${displayPercent(projectsInfo.max_bonuses?.[row.key] || 0)}`,
    };
}

function ProjectName({ row }) {
    return (
        <div className="project-name">
            <span>{row.name}</span>
            <small className="project-desc">{row.desc}</small>
        </div>
    );
}

/** Each section of ``projectSections`` under its heading, its groups drawn by ``ProjectTables``. */
function ProjectSections({ state, kdInfo, projectsInfo, ...tableProps }) {
    return projectSections(state, kdInfo, projectsInfo).map((section) => (
        <div className="projects-section" key={section.key}>
            <h4 className="projects-section-title">{section.title}</h4>
            <small className="projects-section-note">{section.note}</small>
            <ProjectTables groups={section.groups} valueHeader={section.valueHeader} kdInfo={kdInfo}
                projectsInfo={projectsInfo} {...tableProps} />
        </div>
    ));
}

/** One table per category. ``inputs(row)`` gives the cells after the shared ones; ``inputHeaders`` their headers. */
function ProjectTables({ groups, valueHeader, kdInfo, engineersInfo, projectsInfo, inputHeaders, inputs }) {
    return groups.map(({ category, title, rows }) => {
        const blocked = (row) => Boolean(row.locked) || (row.oneTime && row.completed);
        const columns = [
            { header: "Project", align: "left", cell: (row) => <ProjectName row={row} /> },
            { header: "Assigned", className: "assigned-col",
              cell: (row) => (row.locked ? row.locked : projectCells(row, kdInfo, engineersInfo, projectsInfo).assigned),
              span: (row) => (row.locked ? 2 : 1) },
            { header: "Points", cell: (row) => projectCells(row, kdInfo, engineersInfo, projectsInfo).points },
            { header: valueHeader, cell:(row) => projectCells(row, kdInfo, engineersInfo, projectsInfo).value },
            ...inputHeaders.map((header, index) => ({ header, cell: (row) => inputs(row, blocked(row))[index] })),
        ];
        return (
            <div className="projects-category" key={category}>
                {title ? <h5 className="projects-category-title">{title}</h5> : null}
                <GameTable className="game-table projects-table" columns={columns} rows={rows}
                    rowClassName={(row) => (blocked(row) ? "disabled-table-row" : undefined)} />
            </div>
        );
    });
}

function Assign(props) {
    const blank = blankValues(props.state);
    const [assignValues, setAssignValues] = useState(blank);
    const [addValues, setAddValues] = useState(blank);
    const [assignResult, setAssignResult] = useState([]);

    const handleAssignInputChange = (e) => {
        const { name, value } = e.target;
        setAssignValues((previous) => ({ ...previous, [name]: value }));
    };
    const handleAddInputChange = (e) => {
        const { name, value } = e.target;
        setAddValues((previous) => ({ ...previous, [name]: value }));
    };
    const send = (opts) => {
        const updateFunc = () => authFetch('api/projects', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult((previous) => previous.concat(r)));
        props.updateData(['projects', 'kingdom'], [updateFunc]);
    };
    const filled = (values) => Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ""));

    const onAssignClick = () => {
        const assignOpts = filled(assignValues);
        if (Object.keys(assignOpts).length > 0) {
            send({ "assign": assignOpts });
        }
        setAssignValues(blank);
    };
    const onAddClick = () => {
        const addOpts = filled(addValues);
        if (Object.keys(addOpts).length > 0) {
            send({ "add": addOpts });
        }
        setAddValues(blank);
    };
    const OnClearAllClick = () => send({ "clear": Object.keys(blank) });
    const OnClearClick = (e) => send({ "clear": [e.target.name] });

    if (Object.keys(props.engineersInfo).length === 0 || Object.keys(props.kdInfo).length === 0
        || Object.keys(props.projectsInfo).length === 0) {
        return null;
    }
    const total = (values) => Object.values(values).reduce((sum, value) => sum + (parseInt(value || 0) || 0), 0);
    const free = Math.floor(props.projectsInfo.available_engineers || 0);
    // How many engineers one box can take: the free ones, less what the other boxes of the same column already ask for.
    const maxEngineersFor = (values, name) => Math.max(free - (total(values) - (parseInt(values[name] || 0) || 0)), 0);
    const engineersAssigned = total(assignValues);
    const engineersAdded = total(addValues);

    const inputs = (row, blocked) => [
        <AmountInput name={row.key} id={`${row.key}-assign-input`} label={`Assign to ${row.name}`} value={assignValues[row.key]}
            onChange={handleAssignInputChange} max={blocked ? 0 : maxEngineersFor(assignValues, row.key)} soloMax={blocked ? 0 : free} disabled={blocked} />,
        <AmountInput name={row.key} id={`${row.key}-add-input`} label={`Add to ${row.name}`} value={addValues[row.key]}
            onChange={handleAddInputChange} max={blocked ? 0 : maxEngineersFor(addValues, row.key)} soloMax={blocked ? 0 : free} disabled={blocked} />,
        <Button className="remove-button" name={row.key} variant="primary" type="submit" onClick={OnClearClick}
            disabled={props.loading.projects || (props.kdInfo.projects_assigned?.[row.key] || 0) === 0}>
            {props.loading.projects ? "Loading..." : "Remove"}
        </Button>,
    ];
    return (
        <div className="projects">
            <ResultToasts title="Projects Results" results={assignResult} setResults={setAssignResult} />
            <div className="text-box box-tight projects-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Total Engineers</span>
                    <span className="text-box-item-value">{props.engineersInfo.current_engineers?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available Engineers</span>
                    <span className="text-box-item-value">{props.projectsInfo.available_engineers?.toLocaleString()}</span>
                </div>
            </div>
            <ProjectSections state={props.state} kdInfo={props.kdInfo} engineersInfo={props.engineersInfo} projectsInfo={props.projectsInfo}
                inputHeaders={["Assign", "Add", "Remove"]} inputs={inputs} />
            <div className="projects-buttons">
                <Button className="projects-button" variant="primary" type="submit" onClick={onAssignClick} disabled={props.loading.projects}>
                    {props.loading.projects ? "Loading..." : "Assign"}
                </Button>
                <Button className="projects-button" variant="primary" type="submit" onClick={onAddClick} disabled={props.loading.projects}>
                    {props.loading.projects ? "Loading..." : "Add"}
                </Button>
                <Button className="projects-button" variant="primary" type="submit" onClick={OnClearAllClick} disabled={props.loading.projects}>
                    {props.loading.projects ? "Loading..." : "Remove All"}
                </Button>
                {
                    engineersAssigned !== 0
                    ? <h3>Unassigned Engineers: {(props.engineersInfo.current_engineers - engineersAssigned).toLocaleString()}</h3>
                    : engineersAdded !== 0
                        ? <h3>Unassigned Engineers: {(props.projectsInfo.available_engineers - engineersAdded).toLocaleString()}</h3>
                        : null
                }
            </div>
        </div>
    )
}

function Allocate(props) {
    const blank = blankValues(props.state);
    const [assignValues, setAssignValues] = useState(blank);
    const [assignResult, setAssignResult] = useState([]);

    const handleAssignInputChange = (e) => {
        const { name, value } = e.target;
        setAssignValues((previous) => ({ ...previous, [name]: value }));
    };
    const send = (opts) => {
        const updateFunc = () => authFetch('api/projects/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setAssignResult((previous) => previous.concat(r)));
        props.updateData(['kingdom'], [updateFunc]);
    };
    const onSubmitClick = () => send({ "targets": assignValues });
    const handleEnabledChange = (e) => send({ 'enabled': e.target.checked });

    if (Object.keys(props.engineersInfo).length === 0 || Object.keys(props.kdInfo).length === 0
        || Object.keys(props.projectsInfo).length === 0) {
        return null;
    }
    const maxPercent = (name) => Math.max(100 - Object.entries(assignValues).filter(([other]) => other !== name).reduce((sum, [, value]) => sum + (parseFloat(value) || 0), 0), 0);

    const inputs = (row, blocked) => [
        displayPercent(props.kdInfo.projects_target?.[row.key] || 0),
        <AmountInput name={row.key} id={`${row.key}-allocate-input`} label={`Allocate to ${row.name}`} value={assignValues[row.key]}
            onChange={handleAssignInputChange} suffix="%" max={blocked ? 0 : maxPercent(row.key)} soloMax={blocked ? 0 : 100} disabled={blocked} />,
    ];
    return (
        <div className="projects">
            <ResultToasts title="Projects Results" results={assignResult} setResults={setAssignResult} />
            <div className="text-box box-tight projects-box">
                <span>Choose the target allocation of assigned engineers that you would like the auto-spender to assign towards</span>
            </div>
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
                inputHeaders={["Current Allocation", "New Allocation"]} inputs={inputs} />
            <div className="projects-buttons">
                <Button className="auto-projects-button" variant="primary" type="submit" onClick={onSubmitClick} disabled={props.loading.kingdom}>
                    {props.loading.kingdom ? "Loading..." : "Update"}
                </Button>
            </div>
        </div>
    )
}

export default ProjectsContent;
