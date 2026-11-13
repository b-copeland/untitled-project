import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import 'bootstrap/dist/css/bootstrap.css';
import Nav from 'react-bootstrap/Nav';
import Form from 'react-bootstrap/Form';
import Guide from "./guide.js";
import Home from "./home/home.js";
import News from "./home/news.js";
import Galaxy from "./home/galaxy.js";
import Message from "./home/message.js";
import History from "./home/history.js";
import Scores from "./home/scores.js";
import Build from "./build/build.js";
import Settle from "./build/settle.js";
import Structures from "./build/structures.js";
import Military from "./build/military.js";
import Projects from "./build/projects.js";
import BuildMissiles from "./build/buildmissiles.js";
import Conquer from "./conquer/conquer.js";
import Attack from "./conquer/attack.js";
import Spy from "./conquer/spy.js";
import ShareIntel from "./conquer/shareintel.js";
import LaunchMissiles from "./conquer/launchmissiles.js";
import Schedule from "./conquer/schedule.js";
import Primitives from "./conquer/primitives.js";
import Politics from "./politics/politics.js";
import EmpirePolitics from "./politics/empirepolitics.js";
import UniversePolitics from "./politics/universepolitics.js";
import CreateKingdom from "./other/createkingdom.js";
import ViewKingdom from "./other/viewkingdom.js";
import "./help.css";

// Every topic, in the order of the game's own navigation: [id, label, component]. Each page's help section is one topic.
const TOPICS = [
    ["Start here", [["guide", "Guide", Guide]]],
    ["Home", [["home", "Status", Home], ["news", "News", News], ["galaxy", "Galaxy", Galaxy], ["message", "Message", Message], ["history", "History", History], ["scores", "Scores", Scores]]],
    ["Build", [["build", "Overview", Build], ["settle", "Settle", Settle], ["structures", "Structures", Structures], ["military", "Military", Military], ["projects", "Projects", Projects], ["buildmissiles", "Build Missiles", BuildMissiles]]],
    ["Conquer", [["conquer", "Overview", Conquer], ["attack", "Attack", Attack], ["spy", "Spy", Spy], ["shareintel", "Share Intel", ShareIntel], ["launchmissiles", "Launch Missiles", LaunchMissiles], ["schedule", "Schedule", Schedule], ["primitives", "Primitives", Primitives]]],
    ["Politics", [["politics", "Galaxy Politics", Politics], ["empirepolitics", "Empire Politics", EmpirePolitics], ["universepolitics", "Universe Politics", UniversePolitics]]],
    ["Other", [["createkingdom", "Create Kingdom", CreateKingdom], ["viewkingdom", "View Kingdom", ViewKingdom]]],
];
const FLAT = TOPICS.flatMap(([, topics]) => topics);

/**
 * The help, one topic at a time: a list of topics on the left on a wide screen and a drop-down on a narrow one, with
 * Previous / Next at the bottom. It opens on the topic for the page it was asked from (``scrollTarget``) or the link's
 * #hash.
 */
function Help(props) {
    const location = useLocation();
    const [state, setState] = useState({});
    const wanted = props.scrollTarget || location.hash.slice(1);
    const [selected, setSelected] = useState(FLAT.some(([id]) => id === wanted) ? wanted : "guide");

    useEffect(() => {
        fetch('api/state', {keepalive: true}).then(r => r.json()).then(r => setState(r)).catch(
            err => console.log('Failed to fetch state', err)
        );
    }, []);

    const index = FLAT.findIndex(([id]) => id === selected);
    const Topic = FLAT[index][2];

    return (
        <div className="help">
            <aside className="help-topics">
                <Form.Select className="help-select d-lg-none" aria-label="Help topic" value={selected} onChange={(e) => setSelected(e.target.value)}>
                    {TOPICS.map(([group, topics]) => (
                        <optgroup key={group} label={group}>
                            {topics.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                        </optgroup>
                    ))}
                </Form.Select>
                <Nav className="help-nav d-none d-lg-flex" variant="pills" activeKey={selected} onSelect={(key) => setSelected(key)}>
                    {TOPICS.map(([group, topics]) => (
                        <div key={group} className="help-nav-group">
                            <div className="help-nav-title">{group}</div>
                            {topics.map(([id, label]) => <Nav.Link key={id} eventKey={id}>{label}</Nav.Link>)}
                        </div>
                    ))}
                </Nav>
            </aside>
            <article className="help-article">
                <Topic key={selected} state={state} scrollTarget={null} />
                <div className="help-pager">
                    {index > 0
                        ? <button type="button" className="help-pager-link" onClick={() => setSelected(FLAT[index - 1][0])}>&larr; {FLAT[index - 1][1]}</button>
                        : <span />}
                    {index < FLAT.length - 1
                        ? <button type="button" className="help-pager-link" onClick={() => setSelected(FLAT[index + 1][0])}>{FLAT[index + 1][1]} &rarr;</button>
                        : null}
                </div>
            </article>
        </div>
    )
}

export default Help;
