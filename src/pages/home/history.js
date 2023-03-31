import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./history.css";
import Header from "../../components/header";

function getTimeSinceString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.floor(Math.abs(Date.now() - Date.parse(date)) / 3.6e6);
    const days = Math.floor(hours / 24);
    if (hours > 48) {
        return days.toString() + 'd'
    }
    return hours.toString() + 'h';
}

function getNiceTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const dateParse = new Date(date);

    const options = { weekday: 'short', month: 'short', day: 'numeric'};
    return dateParse.toLocaleString('en-us', options);
}

function HistoryContent(props) {
    const [key, setKey] = useState('attack');

    if (Object.keys(props.data.galaxies_inverted).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdoms).length === 0) {
        return null;
    }
    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="attack"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="attack" title="Attack">
          <Attack kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} attackhistory={props.data.attackhistory} loading={props.loading}/>
        </Tab>
        <Tab eventKey="spy" title="Spy">
          <Spy kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} spyhistory={props.data.spyhistory} loading={props.loading} />
        </Tab>
        <Tab eventKey="missiles" title="Missiles">
          <Missiles kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} missilehistory={props.data.missilehistory} loading={props.loading}/>
        </Tab>
        <Tab eventKey="stats" title="Stats">
          <Stats />
        </Tab>
      </Tabs>
    </>
    )
}

function Attack(props) {
    if (props.loading.attackhistory) {
        return <h2>Loading...</h2>;
    }
    const newsRows = props.attackhistory.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kingdoms[newsItem.to]} ({props.galaxies_inverted[newsItem.to]})</td>
            <td>{newsItem.news}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover>
                <thead>
                    <tr>
                    <th>Time</th>
                    <th>Time Since</th>
                    <th>Target</th>
                    <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Spy(props) {
    if (props.loading.spyhistory) {
        return <h2>Loading...</h2>;
    }
    const newsRows = props.spyhistory.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kingdoms[newsItem.to]} ({props.galaxies_inverted[newsItem.to]})</td>
            <td>{newsItem.operation || ""}</td>
            <td>{newsItem.news}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover>
                <thead>
                    <tr>
                    <th>Time</th>
                    <th>Time Since</th>
                    <th>Target</th>
                    <th>Operation</th>
                    <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Missiles(props) {
    if (props.loading.missilehistory) {
        return <h2>Loading...</h2>;
    }
    const newsRows = props.missilehistory.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kingdoms[newsItem.to]} ({props.galaxies_inverted[newsItem.to]})</td>
            <td>{newsItem.news}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover>
                <thead>
                    <tr>
                    <th>Time</th>
                    <th>Time Since</th>
                    <th>Target</th>
                    <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Stats(props) {
    return (
        <h2>Coming Soon...</h2>
    )
}

export default HistoryContent;