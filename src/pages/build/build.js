import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Accordion from 'react-bootstrap/Accordion';
import Table from 'react-bootstrap/Table';
import "./build.css";

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}

function Build(props) {
    if (Object.keys(props.data.mobis).length === 0) {
        return <h2>Loading...</h2> 
    }
    if (Object.keys(props.data.structures).length === 0) {
        return <h2>Loading...</h2> 
    }
    if (Object.keys(props.data.settle).length === 0) {
        return <h2>Loading...</h2> 
    }
    if (Object.keys(props.data.missiles).length === 0) {
        return <h2>Loading...</h2> 
    }
    const getRemainingMultiSpans = (queue) => {
        const remainingSpans = queue.map((itemObj) => {
            var spanItems = [];
            for (const key of Object.keys(itemObj)) {
                if (key != "time") {
                    spanItems.push({"key": key, "value": itemObj[key]})
                }
            }
            const spans = spanItems.map((spanObj) => 
                <div key={itemObj.time + "_" + spanObj.key} className="remaining-timer">
                    <span className="remaining-time-title">{spanObj.key}</span>
                    <span className="remaining-time-value">{Math.floor(spanObj.value).toLocaleString()}</span>
                    <br />
                </div>
            )
            return {"time": itemObj.time, "spans": spans}
        })
        return remainingSpans;
    }
    const settleData = props.data.settle.top_queue.map((queueItem) => 
        <tr key={queueItem.time}>
            <td>{getTimeString(queueItem.time)}</td>
            <td>{queueItem.amount}</td>
        </tr>
    )
    const structuresData = getRemainingMultiSpans(props.data.structures.top_queue).map((queueItem) => 
        <tr key={queueItem.time}>
            <td>{getTimeString(queueItem.time)}</td>
            <td>{queueItem.spans}</td>
        </tr>
    )
    const unitsData = getRemainingMultiSpans(props.data.mobis.top_queue).map((queueItem) => 
        <tr key={queueItem.time}>
            <td>{getTimeString(queueItem.time)}</td>
            <td>{queueItem.spans}</td>
        </tr>
    )
    const missilesData = getRemainingMultiSpans(props.data.missiles.top_queue).map((queueItem) => 
        <tr key={queueItem.time}>
            <td>{getTimeString(queueItem.time)}</td>
            <td>{queueItem.spans}</td>
        </tr>
    )
    return (
    <div className="queue-page">
        <Accordion defaultActiveKey={['0']} alwaysOpen className="queue-accordion">
            <Accordion.Item eventKey="0">
            <Accordion.Header>Settle Queue</Accordion.Header>
            <Accordion.Body>
                {
                    settleData.length > 0
                    ? <Table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Stars</th>
                            </tr>
                        </thead>
                        <tbody>
                            {settleData}
                        </tbody>
                    </Table>
                    : null
                }
            </Accordion.Body>
            </Accordion.Item>
            <Accordion.Item eventKey="1">
            <Accordion.Header>Structures Queue</Accordion.Header>
            <Accordion.Body>
                {
                    structuresData.length > 0
                    ? <Table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Structures</th>
                            </tr>
                        </thead>
                        <tbody>
                            {structuresData}
                        </tbody>
                    </Table>
                    : null
                }
            </Accordion.Body>
            </Accordion.Item>
            <Accordion.Item eventKey="2">
            <Accordion.Header>Units Queue</Accordion.Header>
            <Accordion.Body>
                {
                    unitsData.length > 0
                    ? <Table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Units</th>
                            </tr>
                        </thead>
                        <tbody>
                            {unitsData}
                        </tbody>
                    </Table>
                    : null
                }
            </Accordion.Body>
            </Accordion.Item>
            <Accordion.Item eventKey="3">
            <Accordion.Header>Missiles Queue</Accordion.Header>
            <Accordion.Body>
                {
                    missilesData.length > 0
                    ? <Table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Missiles</th>
                            </tr>
                        </thead>
                        <tbody>
                            {missilesData}
                        </tbody>
                    </Table>
                    : null
                }
            </Accordion.Body>
            </Accordion.Item>
        </Accordion>
    </div>
    );
}

export default Build;