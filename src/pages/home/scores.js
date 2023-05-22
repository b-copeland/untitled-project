import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./scores.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

function Scores(props) {
    const [key, setKey] = useState('points');

    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="points"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="points" title="Points">
          <Points
            data={props.data}
            />
        </Tab>
        <Tab eventKey="networth" title="Networth">
          <Networth
            data={props.data}/>
        </Tab>
        <Tab eventKey="stars" title="Stars">
          <Stars
            data={props.data}/>
        </Tab>
        <Tab eventKey="galaxy" title="Galaxy Networth">
          <GalaxyNetworth
            data={props.data}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"scores"}/>
    </>
    );
}

const kdFullLabel = (kingdoms, galaxiesInverted, kdId) => {
    if (kdId != "") {
        return kingdoms[parseInt(kdId)] + " (" + galaxiesInverted[kdId] + ")"
    } else {
        return "Unknown"
    }
}

function Points(props) {
    const scores = props.data.scores?.points || [];
    const rows = scores.map((row, iter) =>
        <tr key={iter}>
            <td style={{textAlign: "left"}}>{iter + 1}</td>
            <td style={{textAlign: "left"}}>{kdFullLabel(props.data.kingdoms, props.data.galaxies_inverted, row[0])}</td>
            <td style={{textAlign: "right"}}>{row[1].toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover className="scores-table">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Rank</th>
                        <th style={{textAlign: "left"}}>Kingdom</th>
                        <th style={{textAlign: "right"}}>Points</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </Table>
        </div>
    );
}

function Networth(props) {
    const scores = props.data.scores?.networth || [];
    const rows = scores.map((row, iter) =>
        <tr key={iter}>
            <td style={{textAlign: "left"}}>{iter + 1}</td>
            <td style={{textAlign: "left"}}>{kdFullLabel(props.data.kingdoms, props.data.galaxies_inverted, row[0])}</td>
            <td style={{textAlign: "right"}}>{row[1].toLocaleString()}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover className="scores-table">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Rank</th>
                        <th style={{textAlign: "left"}}>Kingdom</th>
                        <th style={{textAlign: "right"}}>Networth</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </Table>
        </div>
    );
}

function Stars(props) {
    const scores = props.data.scores?.stars || [];
    const rows = scores.map((row, iter) =>
        <tr key={iter}>
            <td style={{textAlign: "left"}}>{iter + 1}</td>
            <td style={{textAlign: "left"}}>{kdFullLabel(props.data.kingdoms, props.data.galaxies_inverted, row[0])}</td>
            <td style={{textAlign: "right"}}>{row[1].toLocaleString()}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover className="scores-table">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Rank</th>
                        <th style={{textAlign: "left"}}>Kingdom</th>
                        <th style={{textAlign: "right"}}>Stars</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </Table>
        </div>
    );
}

function GalaxyNetworth(props) {
    const scores = props.data.scores?.galaxy_networth || [];
    const rows = scores.map((row, iter) =>
        <tr key={iter}>
            <td style={{textAlign: "left"}}>{iter + 1}</td>
            <td style={{textAlign: "left"}}>{row[0]}</td>
            <td style={{textAlign: "right"}}>{row[1].toLocaleString()}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover className="scores-table">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Rank</th>
                        <th style={{textAlign: "left"}}>Galaxy</th>
                        <th style={{textAlign: "right"}}>Networth</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </Table>
        </div>
    );
}

export default Scores;