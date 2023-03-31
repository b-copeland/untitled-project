import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./news.css"
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

function NewsContent(props) {
    const [key, setKey] = useState('kingdom');

    if (Object.keys(props.data.galaxies_inverted).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdoms).length === 0) {
        return null;
    }
    const kdNames = props.data.kingdoms;
    const galaxyMap = props.data.galaxies_inverted;
    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="kingdom" title="Kingdom">
          <Kingdom kdNames={kdNames} galaxyMap={galaxyMap} news={props.data.news}/>
        </Tab>
        <Tab eventKey="galaxy" title="Galaxy">
          <Galaxy kdNames={kdNames} galaxyMap={galaxyMap} galaxynews={props.data.galaxynews}/>
        </Tab>
        <Tab eventKey="empire" title="Empire">
          <Empire kdNames={kdNames} galaxyMap={galaxyMap} empirenews={props.data.empirenews}/>
        </Tab>
        <Tab eventKey="universe" title="Universe">
          <Universe universenews={props.data.universenews}/>
        </Tab>
      </Tabs>
    </>
    );
}

function Kingdom(props) {
    if (props.news.length === 0) {
        return null;
    }
    const news = props.news;
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
    if (props.galaxynews.length === 0) {
        return null;
    }
    const news = props.galaxynews;
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
    if (props.empirenews.length === 0) {
        return null;
    }
    const news = props.empirenews;
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

function Universe(props) {
    if (props.universenews.length === 0) {
        return null;
    }
    const news = props.universenews;
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