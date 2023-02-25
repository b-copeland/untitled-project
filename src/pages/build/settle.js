import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import "./settle.css"


function Settle(props) {
    const [settleInput, setSettleInput] = useState();

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
            })
            props.updateData(['settle'], [updateFunc])
            setSettleInput('');
        }
    }
    const settleInfo = props.data.settle;
    return (
        <div className="settle">
            <div className="settle-input">
                <div className="text-box settle-box">
                    <div className="text-box-item">
                        <span className="text-box-item-title">Settle Time</span>
                        <span className="text-box-item-value">12h</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Settle Cost</span>
                        <span className="text-box-item-value">{settleInfo["settle_price"]}</span>
                    </div>
                    <br />
                    <div className="text-box-item">
                        <span className="text-box-item-title">Maximum New Settlements</span>
                        <span className="text-box-item-value">{settleInfo["max_available_settle"]}</span>
                    </div>
                    <div className="text-box-item">
                        <span className="text-box-item-title">Available New Settlements</span>
                        <span className="text-box-item-value">{settleInfo["current_available_settle"]}</span>
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
                {/* <Button variant="primary" type="submit" onClick={onSubmitClick}>
                    Settle
                </Button> */}
            </div>
        </div>
        )
}

export default Settle;