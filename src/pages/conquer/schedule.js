import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./schedule.css";
import Header from "../../components/header";

function Schedule(props) {
    return (
        <>
            <Header data={props.data} />
            <div className="schedule">
            </div>
        </>
    )
}
export default Schedule;