import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./settle.css"
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { SubmitButton } from "../../components/forms";
import { checkCount, firstError } from "../../validation";


function Settle(props) {
    const [settleInput, setSettleInput] = useState("");
    const [settleResults, setSettleResults] = useState([]);

    const settleInfo = props.data.settle;
    // Fine to send only if it is a whole number from 1 up to what can be settled right now.
    const inputError = checkCount(settleInput, { max: settleInfo.current_available_settle || 0, noun: "stars" });
    const blocked = firstError(inputError) || (parseInt(settleInput, 10) > 0 ? null : "Enter how many stars to settle");

    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/settle', {
            method: 'post',
            body: JSON.stringify({ 'settleInput': settleInput }),
        }).then(r => r.json()).then(r => setSettleResults((previous) => previous.concat(r)));
        props.updateData(['settle', 'kingdom'], [updateFunc]);
        setSettleInput('');
    };

    return (
        <>
        <Header data={props.data} />
        <div className="settle">
            <ResultToasts title="Settle Results" results={settleResults} setResults={setSettleResults} />
            <div className="settle-input">
                <div className="text-box settle-box">
                    <div className="text-box-item">
                        <span className="text-box-item-title">Settle Time</span>
                        <span className="text-box-item-value">{(settleInfo.settle_time || 0) / 3600}h</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Settle Cost</span>
                        <span className="text-box-item-value">{settleInfo.settle_price?.toLocaleString()}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Maximum New Settlements</span>
                        <span className="text-box-item-value">{settleInfo.max_available_settle?.toLocaleString()}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Available New Settlements</span>
                        <span className="text-box-item-value">{settleInfo.current_available_settle?.toLocaleString()}</span>
                    </div>
                </div>
                <InputGroup className="settle-input-group" hasValidation>
                    <InputGroup.Text id="settle-input-display">
                        Stars to Settle
                    </InputGroup.Text>
                    <Form.Control
                        id="settle-input"
                        onChange={(e) => setSettleInput(e.target.value)}
                        value={settleInput || ""}
                        placeholder="0"
                        autoComplete="off"
                        inputMode="numeric"
                        isInvalid={Boolean(inputError)}
                    />
                    <Form.Control.Feedback type="invalid">{inputError}</Form.Control.Feedback>
                </InputGroup>
                <SubmitButton loading={props.loading.settle} blocked={blocked} className="settle-button" onClick={onSubmitClick}>
                    Settle
                </SubmitButton>
                {settleInput !== "" && !inputError
                    ? <h3>Settle Cost: {((parseInt(settleInput, 10) || 0) * settleInfo.settle_price).toLocaleString()}</h3>
                    : null}
            </div>
            <HelpButton scrollTarget={"settle"}/>
        </div>
        </>
    );
}

export default Settle;