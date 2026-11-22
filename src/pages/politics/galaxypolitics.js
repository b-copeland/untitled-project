import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./galaxypolitics.css";
import Select from 'react-select';
import HelpButton from "../../components/helpbutton";
import { Panel } from "../../components/planner";
import { KingdomLink } from "../../components/kingdomlink";
import { useWait, lockedVoteText, waitText } from "../../components/wait";
import { displayPercent } from "../../format";

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
            <td><KingdomLink kdId={leaderId} data={props.data}>{kdFullLabel(leaderId)}</KingdomLink></td>
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

/**
 * The round's galaxy policies. A vote counts from the moment it is cast, and the policy only changes at a tally: each
 * tally weighs every vote by how long it was held since the last one. The server says what is active, the votes, and
 * how the time held so far is shared.
 */
function GalaxyPoliticsPolicies(props) {
    const politics = props.data.galaxypolitics || {};
    const policies = politics.policies || [];
    const tallyWait = useWait(politics.next_tally);
    const send = (policy, option) => {
        const updateFunc = async () => authFetch('api/galaxypolitics/policies', {
            method: 'POST',
            body: JSON.stringify({ policy, option }),
        });
        props.updateData(['galaxypolitics'], [updateFunc]);
    };
    return (
        <div className="galaxy-policies">
            <h2>Galaxy Policies</h2>
            {politics.tally_hours
                ? <p className="vote-rule text-muted">
                    Policies change only at a tally, every {politics.tally_hours} hours
                    {tallyWait !== null ? <>; the next is in {waitText(tallyWait)}</> : null}. Each tally counts how long
                    each vote was held since the last one, so a vote counts from the moment you cast it, and you can
                    change it whenever you like. A tie keeps the active option.
                </p>
                : null}
            {policies.map((policy) => (
                <div className="galaxy-policy" key={policy.key}>
                    <h3>{policy.name}</h3>
                    <div className="galaxy-policy-options">
                        {policy.options.map((option) => {
                            const mine = policy.my_vote === option.key;
                            const active = policy.active === option.key;
                            return (
                                <div key={option.key}
                                    className={active ? "text-box galaxy-policy-card galaxy-policy-winner" : "text-box galaxy-policy-card"}>
                                    <span>{option.name}{active ? <span className="galaxy-policy-active"> (active)</span> : null}</span>
                                    <span>{option.desc}</span>
                                    <span className="text-muted">
                                        Votes: {option.votes}. Share of the time held towards the next tally: {displayPercent(option.weight || 0)}
                                    </span>
                                    {props.loading.galaxypolitics
                                        ? <Button className="galaxy-policy-button" variant="primary" disabled>Loading...</Button>
                                        : mine
                                            ? <Button className="galaxy-policy-button" variant="outline-secondary"
                                                onClick={() => send(policy.key, "")}>
                                                Withdraw my vote
                                            </Button>
                                            : <Button className="galaxy-policy-button" variant="primary"
                                                onClick={() => send(policy.key, option.key)}>
                                                Vote
                                            </Button>}
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}
        </div>
    )
}

export default GalaxyPolitics;