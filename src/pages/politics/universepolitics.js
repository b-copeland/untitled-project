import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import "./universepolitics.css";
import Select from 'react-select';

function getTimeSinceString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.floor(Math.abs(Date.parse(date) - Date.now()) / 3.6e6);
    const days = Math.floor(hours / 24);
    if (hours > 48) {
        return days.toString() + 'd'
    }
    return hours.toString() + 'h';
}

function getTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.abs(Date.parse(date) - Date.now()) / 3.6e6;
    if (hours > 24) {
        return getTimeSinceString(date)
    }
    var n = new Date(0, 0);
    n.setSeconds(+hours * 60 * 60);
    return n.toTimeString().slice(0, 8);
}


function UniversePolitics(props) {
    const [buyVotes, setBuyVotes] = useState("");
    const [results, setResults] = useState([]);
    const [policy1Option1Votes, setPolicy1Option1Votes] = useState("");
    const [policy1Option2Votes, setPolicy1Option2Votes] = useState("");
    const [policy2Option1Votes, setPolicy2Option1Votes] = useState("");
    const [policy2Option2Votes, setPolicy2Option2Votes] = useState("");
    const [timeNow, setTimeNow] = useState(new Date())

    const electionStart = new Date(props.data.state.state?.election_start);

    if (electionStart > timeNow && props.data.state.state?.active_policies?.length === 0) {
        return (
            <div className="universe-politics">
                <div className="text-box universe-politics-box">
                    <span>The universe democracy elections have not yet begun.</span>
                    <br />
                    <span>The voting will begin in {getTimeString(props.data.state.state?.election_start)}</span>
                    <br />
                    <span>Voting will last for 1 day</span>
                </div>
            </div>
        )
    }
    if (electionStart > timeNow && props.data.state.state?.active_policies?.length > 0) {
        if (Object.keys(props.data.universepolitics).length === 0) {
            return <h2>Loading...</h2> 
        }
        const winningPolicies = props.data.state.state?.active_policies;
        const winningOptionPolicy1 = (winningPolicies.includes(props.data.universepolitics.desc?.policy_1?.options["1"].name)) ? "1" : "2";
        const winningOptionPolicy2 = (winningPolicies.includes(props.data.universepolitics.desc?.policy_2?.options["1"].name)) ? "1" : "2";
        return (
            <div className="universe-politics">
                <div className="text-box universe-politics-box">
                    <span>The universe democracy elections have finished.</span>
                    <br />
                    <span>Effects will last until the next voting begins in {getTimeString(props.data.state.state?.election_start)}</span>
                    <br />
                    <span>Voting will last for 1 day</span>
                </div>
                <div className="galaxy-policy">
                    <h3>Winning Policies</h3>
                    <div className="galaxy-policy-options">
                        <div className="text-box galaxy-policy-card">
                            <span>{props.data.universepolitics.desc?.policy_1?.options[winningOptionPolicy1].name || "Option 1"}</span>
                            <br />
                            <span>{props.data.universepolitics.desc?.policy_1?.options[winningOptionPolicy1].desc || "Option 1 description"}</span>
                            <br />
                            <span>Your Votes: {props.data.universepolitics.policy_1["option_" + winningOptionPolicy1] || 0}</span>
                            <br />
                        </div>
                        <div className="text-box galaxy-policy-card">
                            <span>{props.data.universepolitics.desc?.policy_2?.options[winningOptionPolicy2].name || "Option 1"}</span>
                            <br />
                            <span>{props.data.universepolitics.desc?.policy_2?.options[winningOptionPolicy2].desc || "Option 1 description"}</span>
                            <br />
                            <span>Your Votes: {props.data.universepolitics.policy_2["option_" + winningOptionPolicy2] || 0}</span>
                            <br />
                        </div>
                    </div>
                </div>
            </div>
        )
    }
    const onSubmitClick = (e)=>{
        if (buyVotes > 0) {
            let opts = {
                'votes': buyVotes,
            };
            const updateFunc = () => authFetch('api/votes', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => {setResults(results.concat(r))})
            props.updateData(['kingdom'], [updateFunc])
            setBuyVotes('');
        }
    }
    const onClickVotePolicy1Option1 = () => {
        const opts = {
            "policy": "policy_1",
            "option": "option_1",
            "votes": policy1Option1Votes,
        };
        const updateFunc = async () => authFetch('api/universepolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['universepolitics'], [updateFunc]);
    };
    const onClickVotePolicy1Option2 = () => {
        const opts = {
            "policy": "policy_1",
            "option": "option_2",
            "votes": policy1Option2Votes,
        };
        const updateFunc = async () => authFetch('api/universepolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['universepolitics'], [updateFunc]);
    };
    const onClickVotePolicy2Option1 = () => {
        const opts = {
            "policy": "policy_2",
            "option": "option_1",
            "votes": policy2Option1Votes,
        };
        const updateFunc = async () => authFetch('api/universepolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['universepolitics'], [updateFunc]);
    };
    const onClickVotePolicy2Option2 = () => {
        const opts = {
            "policy": "policy_2",
            "option": "option_2",
            "votes": policy2Option2Votes,
        };
        const updateFunc = async () => authFetch('api/universepolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['universepolitics'], [updateFunc]);
    };

    const handleBuyVotesInput = (e) => {
        setBuyVotes(e.target.value);
    }
    const handlePolicy1Option1Input = (e) => {
        setPolicy1Option1Votes(e.target.value);
    }
    const handlePolicy1Option2Input = (e) => {
        setPolicy1Option2Votes(e.target.value);
    }
    const handlePolicy2Option1Input = (e) => {
        setPolicy2Option1Votes(e.target.value);
    }
    const handlePolicy2Option2Input = (e) => {
        setPolicy2Option2Votes(e.target.value);
    }
    const calcVotesCosts = (input) => parseInt(input) * 10000
    const toasts = results.map((result, index) =>
        <Toast
            key={index}
            onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
            show={true}
            bg={result.status === "success" ? "success" : "warning"}
        >
            <Toast.Header>
                <strong className="me-auto">Votes Result</strong>
            </Toast.Header>
            <Toast.Body>{result.message}</Toast.Body>
        </Toast>
    )
    return (
        <div className="universe-politics">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="text-box universe-politics-box">
                <span>The universe democracy elections have begun!</span>
                <br />
                <span>The voting will end in {getTimeString(props.data.state.state?.election_end)}</span>
                <br />
                <span>Effects will last for 6 days</span>
            </div>
            <div className="text-box universe-votes-box">
                <span>You must buy votes to participate in the election. Each vote costs 10,000 money</span>
                <br />
                <span>Unused votes: {props.data.kingdom.votes?.toLocaleString()}</span>
                <br />
                <InputGroup className="buy-votes-input-group">
                    <InputGroup.Text id="buy-votes-input-display">
                        Votes
                    </InputGroup.Text>
                    <Form.Control 
                        id="buy-votes-input"
                        onChange={handleBuyVotesInput}
                        value={buyVotes || ""} 
                        placeholder="0"
                    />
                </InputGroup>
                {props.loading.kingdom
                ? <Button className="buy-votes-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="buy-votes-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Buy
                </Button>
                }
                {
                    buyVotes !== ""
                    ? <h3>Votes Cost: {calcVotesCosts(buyVotes).toLocaleString()}</h3>
                    : null
                }   
            </div>
            <div className="galaxy-policy">
                <h3>{props.data.universepolitics.desc?.policy_1?.name || "Policy 1"}</h3>
                <div className="galaxy-policy-options">
                    <div className="text-box galaxy-policy-card">
                        <span>{props.data.universepolitics.desc?.policy_1?.options["1"].name || "Option 1"}</span>
                        <br />
                        <span>{props.data.universepolitics.desc?.policy_1?.options["1"].desc || "Option 1 description"}</span>
                        <br />
                        <span>Your Votes: {props.data.universepolitics.policy_1?.option_1 || 0}</span>
                        <br />
                        <InputGroup className="cast-votes-input-group">
                            <InputGroup.Text id="cast-votes-input-display">
                                Votes
                            </InputGroup.Text>
                            <Form.Control 
                                id="cast-votes-policy-1-option-1-input"
                                onChange={handlePolicy1Option1Input}
                                value={policy1Option1Votes || ""} 
                                placeholder="0"
                            />
                        </InputGroup>
                        {
                            props.loading.universepolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy1Option1}
                                // disabled={(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "1")}
                            >
                                Cast Votes
                            </Button>
                        }
                    </div>
                    <div className="text-box galaxy-policy-card">
                        <span>{props.data.universepolitics.desc?.policy_1?.options["2"].name || "Option 2"}</span>
                        <br />
                        <span>{props.data.universepolitics.desc?.policy_1?.options["2"].desc || "Option 2 description"}</span>
                        <br />
                        <span>Your Votes: {props.data.universepolitics.policy_1?.option_2 || 0}</span>
                        <br />
                        <InputGroup className="cast-votes-input-group">
                            <InputGroup.Text id="cast-votes-input-display">
                                Votes
                            </InputGroup.Text>
                            <Form.Control 
                                id="cast-votes-policy-1-option-2-input"
                                onChange={handlePolicy1Option2Input}
                                value={policy1Option2Votes || ""} 
                                placeholder="0"
                            />
                        </InputGroup>
                        {
                            props.loading.universepolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy1Option2}
                                // disabled={(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "2")}
                            >
                                Cast Votes
                            </Button>
                        }
                    </div>
                </div>
            </div>
            <div className="galaxy-policy">
                <h3>{props.data.universepolitics.desc?.policy_2?.name || "Policy 2"}</h3>
                <div className="galaxy-policy-options">
                    <div className="text-box galaxy-policy-card">
                        <span>{props.data.universepolitics.desc?.policy_2?.options["1"].name || "Option 1"}</span>
                        <br />
                        <span>{props.data.universepolitics.desc?.policy_2?.options["1"].desc || "Option 1 description"}</span>
                        <br />
                        <span>Your Votes: {props.data.universepolitics.policy_2?.option_1 || 0}</span>
                        <br />
                        <InputGroup className="cast-votes-input-group">
                            <InputGroup.Text id="cast-votes-input-display">
                                Votes
                            </InputGroup.Text>
                            <Form.Control 
                                id="cast-votes-policy-2-option-1-input"
                                onChange={handlePolicy2Option1Input}
                                value={policy2Option1Votes || ""} 
                                placeholder="0"
                            />
                        </InputGroup>
                        {
                            props.loading.universepolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy2Option1}
                                // disabled={(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "1")}
                            >
                                Cast Votes
                            </Button>
                        }
                    </div>
                    <div className="text-box galaxy-policy-card">
                        <span>{props.data.universepolitics.desc?.policy_2?.options["2"].name || "Option 2"}</span>
                        <br />
                        <span>{props.data.universepolitics.desc?.policy_2?.options["2"].desc || "Option 2 description"}</span>
                        <br />
                        <span>Your Votes: {props.data.universepolitics.policy_2?.option_2 || 0}</span>
                        <br />
                        <InputGroup className="cast-votes-input-group">
                            <InputGroup.Text id="cast-votes-input-display">
                                Votes
                            </InputGroup.Text>
                            <Form.Control 
                                id="cast-votes-policy-2-option-2-input"
                                onChange={handlePolicy2Option2Input}
                                value={policy2Option2Votes || ""} 
                                placeholder="0"
                            />
                        </InputGroup>
                        {
                            props.loading.universepolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy2Option2}
                                // disabled={(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "2")}
                            >
                                Cast Votes
                            </Button>
                        }
                    </div>
                </div>
            </div>
        </div>
    )
}

export default UniversePolitics;