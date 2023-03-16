import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import "./createkingdom.css"

function CreateKingdom(props) {
    const [kdName, setKdName] = useState("");
    const [kdNameMessage, setKdNameMessage] = useState("");
    
    const handleNameInput = (e) => {
        setKdName(e.target.value);
    }

    const onSubmitNameClick = (e)=>{
        if (kdName != "") {
            let opts = {
                'kdName': kdName,
            };
            setKdNameMessage("")
            const updateFunc = () => authFetch('api/createkingdom', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setKdNameMessage(r))
            props.updateData(['kingdomid'], [updateFunc])
        }
    }

    return (
        <div>
        {
            (props.kingdomid.kd_id === "")
            ? <div>
                <h2>Choose a kingdom name</h2>
                <InputGroup className="kd-name-group">
                    <InputGroup.Text id="kd-name-input-display">
                        Kingdom Name
                    </InputGroup.Text>
                    <Form.Control 
                        id="kd-name-input"
                        onChange={handleNameInput}
                        value={kdName || ""} 
                        placeholder=""
                    />
                </InputGroup>
                {props.loading.kingdomid
                ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitNameClick}>
                    Submit
                </Button>
                }
                {
                    kdNameMessage !== ""
                    ? <h4>{kdNameMessage}</h4>
                    : null
                }
            </div>
            : <div>

            </div>
        }
        </div>
    )
}

export default CreateKingdom;