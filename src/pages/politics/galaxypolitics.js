import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./galaxypolitics.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { Panel } from "../../components/planner";
import { useWait, lockedVoteText } from "../../components/wait";

/** The sentence under a vote: why it is locked and until when, or (unless ``lockedOnly``) how long a change holds. */
function VoteRule({ data, wait, lockedOnly = false }) {
    const locked = lockedVoteText(wait);
    if (locked) return <p className="vote-locked">{locked}</p>;
    const hours = data.galaxypolitics?.vote_cooldown_hours;
    return hours && !lockedOnly ? <p className="vote-rule text-muted">Once you change a vote, it stays for {hours} hours.</p> : null;
}

function GalaxyPolitics(props) {
    const [key, setKey] = useState('leader');

    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="leader"
        variant="tabs"
      >
        <Tab eventKey="leader" title="Leader">
          <GalaxyPoliticsLeader
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
            />
        </Tab>
        <Tab eventKey="policies" title="Policies">
          <GalaxyPoliticsPolicies
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"politics"}/>
    </>
    );
}

function GalaxyPoliticsLeader(props) {
    const [selected, setSelected] = useState(props.initialKd || undefined);
    const leaderWait = useWait(props.data.galaxypolitics?.vote_unlocks_at?.leader);
    const kdFullLabel = (kdId) => {
        if (kdId != undefined) {
            return props.data.kingdoms[kdId] + " (" + props.data.galaxies_inverted[kdId] + ")"
        } else {
            return "Nobody"
        }
    }
    const handleChange = (selectedOption) => {
        setSelected(selectedOption.value);
    };
    const onClickVote = () => {
        if (selected != undefined && leaderWait === null) {
            const opts = {
                "selected": selected,
            };
            const updateFunc = async () => authFetch('api/galaxypolitics/leader', {
                method: 'POST',
                body: JSON.stringify(opts)
            })
            props.updateData(['galaxypolitics'], [updateFunc]);
        }
    };
    if (Object.keys(props.data.galaxies_inverted).length === 0 || Object.keys(props.data.kingdom).length === 0) {
        return <h2>Loading...</h2> 
    }
    const kingdomOptions = props.data.galaxies[props.data.galaxies_inverted[props.data.kingdom.kdId]].map((kdId) => {
        return {"value": kdId, "label": kdFullLabel(kdId)}
    })
    const currentLeaderVote = props.data.galaxypolitics.votes?.leader[props.data.kingdom.kdId];
    const currentLeaderVoteLabel = kdFullLabel(currentLeaderVote);

    const calcGalaxyLeaderVotes = () => {
        let votes = {};
        let leaderVotes = props.data.galaxypolitics.votes?.leader;
        for (const voter in leaderVotes) {
            const vote = leaderVotes[voter];
            if (votes.hasOwnProperty(vote)) {
                votes[vote]++
            } else {
                votes[vote] = 1
            }
        }
        return votes
    }
    const galaxyLeaderVotes = calcGalaxyLeaderVotes();
    
    const galaxyLeaderRows = Object.keys(galaxyLeaderVotes).map((leaderId) =>
        <tr key={leaderId}>
            <td>{kdFullLabel(leaderId)}</td>
            <td>{galaxyLeaderVotes[leaderId]}</td>
            <td>{leaderId === props.data.galaxypolitics.leader ? "X" : ""}</td>
        </tr>
    );
    return (
        <div className="galaxy-politics panel-grid">
            <Panel title="Your vote">
            <form className="galaxy-leader-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a galaxy leader
                </label>
                <Select
                    id="select-kingdom"
                    className="galaxy-leader-select"
                    options={kingdomOptions}
                    onChange={handleChange}
                    autoFocus={true}
                    defaultValue={kingdomOptions.filter(option => option.value === props.initialKd)}     
                    isSearchable={false}
                    styles={{
                        control: (baseStyles, state) => ({
                            ...baseStyles,
                            borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                            backgroundColor: 'var(--bs-body-bg)',
                        }),
                        placeholder: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-primary-text)',
                        }),
                        input: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                        option: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                            color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                        }),
                        menuList: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: 'var(--bs-secondary-bg)',
                            // borderColor: 'var(--bs-secondary-bg)',
                        }),
                        singleValue: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                    }}
                />
            </form>
            <p className="galaxy-leader-current">You are currently voting for: <strong>{currentLeaderVoteLabel}</strong></p>
            <VoteRule data={props.data} wait={leaderWait} />
            {
                props.loading.galaxypolitics
                ? <Button className="galaxy-leader-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="galaxy-leader-button" variant="primary" type="submit" onClick={onClickVote}
                    disabled={leaderWait !== null} title={lockedVoteText(leaderWait) || undefined}>
                    Vote
                </Button>
            }
            </Panel>
            <Panel title="Votes">
            <Table hover className="galaxy-leader-table">
                <thead>
                    <tr>
                        <th>Kingdom</th>
                        <th>Votes</th>
                        <th>Is Leader?</th>
                    </tr>
                </thead>
                <tbody>
                    {galaxyLeaderRows}
                </tbody>
            </Table>
            </Panel>
        </div>
    )
}

function GalaxyPoliticsPolicies(props) {
    const policyWait = { policy_1: useWait(props.data.galaxypolitics?.vote_unlocks_at?.policy_1), policy_2: useWait(props.data.galaxypolitics?.vote_unlocks_at?.policy_2) };
    const onClickVotePolicy1Option1 = () => {
        const opts = {
            "policy": "policy_1",
            "option": "option_1",
        };
        const updateFunc = async () => authFetch('api/galaxypolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        })
        props.updateData(['galaxypolitics'], [updateFunc]);
    };
    const onClickVotePolicy1Option2 = () => {
        const opts = {
            "policy": "policy_1",
            "option": "option_2",
        };
        const updateFunc = async () => authFetch('api/galaxypolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        })
        props.updateData(['galaxypolitics'], [updateFunc]);
    };
    const onClickVotePolicy2Option1 = () => {
        const opts = {
            "policy": "policy_2",
            "option": "option_1",
        };
        const updateFunc = async () => authFetch('api/galaxypolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        })
        props.updateData(['galaxypolitics'], [updateFunc]);
    };
    const onClickVotePolicy2Option2 = () => {
        const opts = {
            "policy": "policy_2",
            "option": "option_2",
        };
        const updateFunc = async () => authFetch('api/galaxypolitics/policies', {
            method: 'POST',
            body: JSON.stringify(opts)
        })
        props.updateData(['galaxypolitics'], [updateFunc]);
    };
    const calcVotes = (votesObj, idToCount) => {
        var count = 0;
        for (const voter in votesObj) {
            if (votesObj[voter] == idToCount) {
                count++
            }
        }
        return count;
    }
    const countPolicy1Option1 = calcVotes(props.data.galaxypolitics.votes?.policy_1, "1");
    const countPolicy1Option2 = calcVotes(props.data.galaxypolitics.votes?.policy_1, "2");
    const policy1Winner = props.data.galaxypolitics.policy_1_winner;
    const countPolicy2Option1 = calcVotes(props.data.galaxypolitics.votes?.policy_2, "1");
    const countPolicy2Option2 = calcVotes(props.data.galaxypolitics.votes?.policy_2, "2");
    const policy2Winner = props.data.galaxypolitics.policy_2_winner;
    return (
        <div className="galaxy-policies">
            <h2>Galaxy Policies</h2>
            {props.data.galaxypolitics?.vote_cooldown_hours
                ? <p className="vote-rule text-muted">Once you change a vote, it stays for {props.data.galaxypolitics.vote_cooldown_hours} hours.</p> : null}
            <div className="galaxy-policy">
                <h3>{props.data.galaxypolitics.desc?.policy_1?.name || "Policy 1"}</h3>
                <VoteRule data={props.data} wait={policyWait.policy_1} lockedOnly />
                <div className="galaxy-policy-options">
                    <div className={(policy1Winner === "1") ? "text-box galaxy-policy-card galaxy-policy-winner" : "text-box galaxy-policy-card"}>
                        <span>{props.data.galaxypolitics.desc?.policy_1?.options["1"].name || "Option 1"}</span>
                        <br />
                        <span>{props.data.galaxypolitics.desc?.policy_1?.options["1"].desc || "Option 1 description"}</span>
                        <br />
                        <span>Current Votes: {countPolicy1Option1}</span>
                        {
                            props.loading.galaxypolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy1Option1}
                                disabled={(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "1") || policyWait.policy_1 !== null}
                                title={lockedVoteText(policyWait.policy_1) || undefined}
                            >
                                {(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "1") ? "Already Voting" : "Vote"}
                            </Button>
                        }
                    </div>
                    <div className={(policy1Winner === "2") ? "text-box galaxy-policy-card galaxy-policy-winner" : "text-box galaxy-policy-card"}>
                        <span>{props.data.galaxypolitics.desc?.policy_1?.options["2"].name || "Option 2"}</span>
                        <br />
                        <span>{props.data.galaxypolitics.desc?.policy_1?.options["2"].desc || "Option 2 description"}</span>
                        <br />
                        <span>Current Votes: {countPolicy1Option2}</span>
                        {
                            props.loading.galaxypolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy1Option2}
                                disabled={(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "2") || policyWait.policy_1 !== null}
                                title={lockedVoteText(policyWait.policy_1) || undefined}
                            >
                                {(props.data.galaxypolitics.votes?.policy_1[props.data.kingdomid.kd_id] === "2") ? "Already Voting" : "Vote"}
                            </Button>
                        }
                    </div>
                </div>
            </div>
            <div className="galaxy-policy">
                <h3>{props.data.galaxypolitics.desc?.policy_2?.name || "Policy 2"}</h3>
                <VoteRule data={props.data} wait={policyWait.policy_2} lockedOnly />
                <div className="galaxy-policy-options">
                    <div className={(policy2Winner === "1") ? "text-box galaxy-policy-card galaxy-policy-winner" : "text-box galaxy-policy-card"}>
                        <span>{props.data.galaxypolitics.desc?.policy_2?.options["1"].name || "Option 1"}</span>
                        <br />
                        <span>{props.data.galaxypolitics.desc?.policy_2?.options["1"].desc || "Option 1 description"}</span>
                        <br />
                        <span>Current Votes: {countPolicy2Option1}</span>
                        {
                            props.loading.galaxypolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy2Option1}
                                disabled={(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "1") || policyWait.policy_2 !== null}
                                title={lockedVoteText(policyWait.policy_2) || undefined}
                            >
                                {(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "1") ? "Already Voting" : "Vote"}
                            </Button>
                        }
                    </div>
                    <div className={(policy2Winner === "2") ? "text-box galaxy-policy-card galaxy-policy-winner" : "text-box galaxy-policy-card"}>
                        <span>{props.data.galaxypolitics.desc?.policy_2?.options["2"].name || "Option 2"}</span>
                        <br />
                        <span>{props.data.galaxypolitics.desc?.policy_2?.options["2"].desc || "Option 2 description"}</span>
                        <br />
                        <span>Current Votes: {countPolicy2Option2}</span>
                        {
                            props.loading.galaxypolitics
                            ? <Button className="galaxy-policy-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button
                                className="galaxy-policy-button"
                                variant="primary"
                                type="submit"
                                onClick={onClickVotePolicy2Option2}
                                disabled={(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "2") || policyWait.policy_2 !== null}
                                title={lockedVoteText(policyWait.policy_2) || undefined}
                            >
                                {(props.data.galaxypolitics.votes?.policy_2[props.data.kingdomid.kd_id] === "2") ? "Already Voting" : "Vote"}
                            </Button>
                        }
                    </div>
                </div>
            </div>
        </div>
    )
}

export default GalaxyPolitics;