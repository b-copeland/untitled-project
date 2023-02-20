import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./news.css"

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

function NewsContent() {
    const [key, setKey] = useState('kingdom');
    const [galaxyMap, setGalaxyMap] = useState({});
    const [kdNames, setKdNames] = useState({});

    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/kingdoms").then(r => r.json()).then(r => setKdNames(r));
            await authFetch("api/galaxies_inverted").then(r => r.json()).then(r => setGalaxyMap(r));
        }
        fetchData();
    }, [])
    if (Object.keys(galaxyMap).length === 0) {
        return null;
    }
    if (Object.keys(kdNames).length === 0) {
        return null;
    }
    return (
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="kingdom" title="Kingdom">
          <Kingdom kdNames={kdNames} galaxyMap={galaxyMap}/>
        </Tab>
        <Tab eventKey="galaxy" title="Galaxy">
          <Galaxy kdNames={kdNames} galaxyMap={galaxyMap}/>
        </Tab>
        <Tab eventKey="empire" title="Empire">
          <Empire kdNames={kdNames} galaxyMap={galaxyMap}/>
        </Tab>
        <Tab eventKey="universe" title="Universe">
          <Universe />
        </Tab>
      </Tabs>
    );
}

function Kingdom(props) {
    const [news, setNews] = useState([]);
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/news").then(r => r.json()).then(r => setNews(r));
        }
        fetchData();
    }, [])
    if (news.length === 0) {
        return null;
    }
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kdNames[newsItem.from]} ({props.galaxyMap[newsItem.from]})</td>
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
                    <th>From</th>
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Galaxy(props) {
    const [news, setNews] = useState([]);
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/galaxynews").then(r => r.json()).then(r => setNews(r));
        }
        fetchData();
    }, [])
    if (news.length === 0) {
        return null;
    }
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kdNames[newsItem.from]} ({props.galaxyMap[newsItem.from]})</td>
            <td>{props.kdNames[newsItem.to]} ({props.galaxyMap[newsItem.to]})</td>
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
                    <th>From</th>
                    <th>To</th>
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Empire(props) {
    const [news, setNews] = useState([]);
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/empirenews").then(r => r.json()).then(r => setNews(r));
        }
        fetchData();
    }, [])
    if (news.length === 0) {
        return null;
    }
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kdNames[newsItem.to]} ({props.galaxyMap[newsItem.to]})</td>
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
                    <th>To</th>
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Universe() {
    const [news, setNews] = useState([]);
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/universenews").then(r => r.json()).then(r => setNews(r));
        }
        fetchData();
    }, [])
    if (news.length === 0) {
        return null;
    }
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
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
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

export default NewsContent;