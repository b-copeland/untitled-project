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


function Settle(props) {
    const [settleInput, setSettleInput] = useState("");
    const [settleResults, setSettleResults] = useState([]);

    const handleSettleInput = (e) => {
        setSettleInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (settleInput > 0) {
            let opts = {
                'settleInput': settleInput,
            };
            const updateFunc = () => authFetch('api/settle', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setSettleResults(settleResults.concat(r)))
            props.updateData(['settle', 'kingdom'], [updateFunc])
            setSettleInput('');
        }
    }
    const settleInfo = props.data.settle;
    const toasts = settleResults.map((results, index) =>
        <Toast
            key={index}
            onClose={(e) => setSettleResults(settleResults.slice(0, index).concat(settleResults.slice(index + 1, 999)))}
            show={true}
            bg={results.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Settle Results</strong>
            </Toast.Header>
            <Toast.Body>{results.message}</Toast.Body>
        </Toast>
    )
    const calcSettleCosts = (input) => parseInt(input) * settleInfo.settle_price
    return (
        <>
        <Header data={props.data} />
        <div className="settle">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="settle-input">
                <div className="text-box settle-box">
                    <div className="text-box-item">
                        <span className="text-box-item-title">Settle Time</span>
                        <span className="text-box-item-value">12h</span>
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
                <InputGroup className="settle-input-group">
                    <InputGroup.Text id="settle-input-display">
                        Stars to Settle
                    </InputGroup.Text>
                    <Form.Control 
                        id="settle-input"
                        onChange={handleSettleInput}
                        value={settleInput || ""} 
                        placeholder="0"
                        autoComplete="off"
                    />
                </InputGroup>
                {props.loading.settle
                ? <Button className="settle-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="settle-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Settle
                </Button>
                }
                {
                    settleInput !== ""
                    ? <h3>Settle Cost: {calcSettleCosts(settleInput).toLocaleString()}</h3>
                    : null
                }   
            </div>
        </div>
        </>
        )
}

export default Settle;