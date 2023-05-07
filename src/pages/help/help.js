import React, { useMemo, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Dropdown from 'react-bootstrap/Dropdown';
import DropdownButton from 'react-bootstrap/DropdownButton';
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

function Help(props) {
    let location = useLocation();
    const [state, setState] = useState({});
    const [scrollTarget, setScrollTarget] = useState(props.scrollTarget || location.hash.slice(1));

    useEffect(() => {
        const fetchData = () => {
            fetch('api/state', {keepalive: true}).then(
                r => r.json()
            ).then(r => setState(r)).catch(
                err => {
                    console.log('Failed to fetch state');
                    console.log(err);
                }
            );
        }
        fetchData();
    }, []);
    return (
      <>
        <div id="top" />
        <div className="help-dropdown-div">
          <Dropdown
              id={`help-dropdown`}
              size="sm"
              variant="secondary"
              >
              <Dropdown.Toggle>
                  Go To
              </Dropdown.Toggle>

              <Dropdown.Menu
                  className="help-dropdown-button"
              >
                  <Dropdown.Item href="#top">Top</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Home</Dropdown.Header>
                  <Dropdown.Item href="#home">Home</Dropdown.Item>
                  <Dropdown.Item href="#news">News</Dropdown.Item>
                  <Dropdown.Item href="#galaxy">Galaxy</Dropdown.Item>
                  <Dropdown.Item href="#message">Message</Dropdown.Item>
                  <Dropdown.Item href="#history">History</Dropdown.Item>
                  <Dropdown.Item href="#scores">Scores</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Build</Dropdown.Header>
                  <Dropdown.Item href="#build">Build</Dropdown.Item>
                  <Dropdown.Item href="#settle">Settle</Dropdown.Item>
                  <Dropdown.Item href="#structures">Structures</Dropdown.Item>
                  <Dropdown.Item href="#military">Military</Dropdown.Item>
                  <Dropdown.Item href="#projects">Projects</Dropdown.Item>
                  <Dropdown.Item href="#buildmissiles">Build Missiles</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Conquer</Dropdown.Header>
                  <Dropdown.Item href="#conquer">Conquer</Dropdown.Item>
                  <Dropdown.Item href="#attack">Attack</Dropdown.Item>
                  <Dropdown.Item href="#spy">Spy</Dropdown.Item>
                  <Dropdown.Item href="#shareintel">Share Intel</Dropdown.Item>
                  <Dropdown.Item href="#launchmissiles">Launch Missiles</Dropdown.Item>
                  <Dropdown.Item href="#schedule">Schedule</Dropdown.Item>
                  <Dropdown.Item href="#primitives">Primitives</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Politics</Dropdown.Header>
                  <Dropdown.Item href="#politics">Politics</Dropdown.Item>
                  <Dropdown.Item href="#empirepolitics">Empire Politics</Dropdown.Item>
                  <Dropdown.Item href="#universepolitics">Universe Politics</Dropdown.Item>
                  <Dropdown.Divider />
                  <Dropdown.Header>Other</Dropdown.Header>
                  <Dropdown.Item href="#createkingdom">Create Kingdom</Dropdown.Item>
                  <Dropdown.Item href="#viewkingdom">View Kingdom</Dropdown.Item>
              </Dropdown.Menu>
          </Dropdown>
        </div>
        <div className="help">
            <div className="help-contents">
                <Home state={state} scrollTarget={scrollTarget}/>
                <News state={state} scrollTarget={scrollTarget}/>
                <Galaxy state={state} scrollTarget={scrollTarget}/>
                <Message state={state} scrollTarget={scrollTarget}/>
                <History state={state} scrollTarget={scrollTarget}/>
                <Scores state={state} scrollTarget={scrollTarget}/>
                <Build state={state} scrollTarget={scrollTarget}/>
                <Settle state={state} scrollTarget={scrollTarget}/>
                <Structures state={state} scrollTarget={scrollTarget}/>
                <Military state={state} scrollTarget={scrollTarget}/>
                <Projects state={state} scrollTarget={scrollTarget}/>
                <BuildMissiles state={state} scrollTarget={scrollTarget}/>
                <Conquer state={state} scrollTarget={scrollTarget}/>
                <Attack state={state} scrollTarget={scrollTarget}/>
                <Spy state={state} scrollTarget={scrollTarget}/>
                <ShareIntel state={state} scrollTarget={scrollTarget}/>
                <LaunchMissiles state={state} scrollTarget={scrollTarget}/>
                <Schedule state={state} scrollTarget={scrollTarget}/>
                <Primitives state={state} scrollTarget={scrollTarget}/>
                <Politics state={state} scrollTarget={scrollTarget}/>
                <EmpirePolitics state={state} scrollTarget={scrollTarget}/>
                <UniversePolitics state={state} scrollTarget={scrollTarget}/>
                <CreateKingdom state={state} scrollTarget={scrollTarget}/>
                <ViewKingdom state={state} scrollTarget={scrollTarget}/>
            </div>
        </div>
      </>
    )
}

export default Help;