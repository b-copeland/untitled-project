import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./empirepolitics.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

function EmpirePolitics(props) {
    return (
        <>
        <Header data={props.data} />
        <h2>Coming Soon</h2>
        <HelpButton scrollTarget={"empirepolitics"}/>
        </>
    )
}

export default EmpirePolitics;