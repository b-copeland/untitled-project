import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import "./spy.css";

function Spy(props) {
    return <h2>Spy Page</h2>
}

export default Spy;