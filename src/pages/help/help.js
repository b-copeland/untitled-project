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

const ScrollToHashElement = () => {
    let location = useLocation();
  
    let hashElement = useMemo(() => {
      let hash = location.hash;
      const removeHashCharacter = (str) => {
        const result = str.slice(1);
        return result;
      };
  
      if (hash) {
        let element = document.getElementById(removeHashCharacter(hash));
        return element;
      } else {
        return null;
      }
    }, [location]);
  
    useEffect(() => {
      if (hashElement) {
        hashElement.scrollIntoView({
          behavior: "smooth",
          // block: "end",
          inline: "nearest",
        });
      }
    }, [hashElement]);
  
    return null;
  };

function Help(props) {
    const [state, setState] = useState({});
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
        <div className="help">
            <ScrollToHashElement />
            <h1>Help</h1>
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
            <div className="help-contents">
                <Home state={state}/>
                <News state={state}/>
                <Galaxy state={state}/>
                <Message state={state}/>
                <History state={state}/>
                <Scores state={state}/>
                <Build state={state}/>
                <Settle state={state}/>
                <Structures state={state}/>
                <Military state={state}/>
                <Projects state={state}/>
                <BuildMissiles state={state}/>
                <Conquer state={state}/>
                <Attack state={state}/>
                <Spy state={state}/>
                <ShareIntel state={state}/>
                <LaunchMissiles state={state}/>
                <Schedule state={state}/>
                <Primitives state={state}/>
                <Politics state={state}/>
                <EmpirePolitics state={state}/>
                <UniversePolitics state={state}/>
                <CreateKingdom state={state}/>
                <ViewKingdom state={state}/>
            </div>
        </div>
    )
}

export default Help;