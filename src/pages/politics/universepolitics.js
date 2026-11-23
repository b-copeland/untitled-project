import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import { AmountInput } from "../../components/forms";
import "./universepolitics.css";
import "./galaxypolitics.css";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { Panel } from "../../components/planner";
import { useWait, waitText } from "../../components/wait";
import { playFlourish } from "../../components/flourish";

// The options in force this browser last revealed, so the curtains open once for each new result.
const SEEN_KEY = "farsteel-seen-election";

/** Opens the curtains on the options in force when they differ from what this browser last showed. */
function useElectionReveal(active) {
    const shown = active ? active.map((option) => option.key).sort().join(",") : null;
    useEffect(() => {
        if (!shown) {
            return;
        }
        let seen = null;
        try {
            seen = window.localStorage.getItem(SEEN_KEY);
            window.localStorage.setItem(SEEN_KEY, shown);
        } catch (error) {
            return;  // No storage (a private window): no way to show it only once, so do not show it.
        }
        if (seen !== shown) {
            playFlourish({ kind: "election", lines: active.map((option) => `${option.policy_name}: ${option.name}`) });
        }
    }, [shown]); // eslint-disable-line react-hooks/exhaustive-deps
}

/**
 * Universe politics. The server sends the ballot (the open election's policies, or the next one's), this kingdom's own
 * votes, and the options in force; nobody sees anyone else's votes.
 */
function UniversePolitics(props) {
    const [buyVotes, setBuyVotes] = useState("");
    const [results, setResults] = useState([]);
    const [amounts, setAmounts] = useState({});
    const universe = props.data.universepolitics || {};
    const election = universe.election || {};
    const opensIn = useWait(election.open ? null : election.start);
    const closesIn = useWait(election.open ? election.end : null);
    useElectionReveal(universe.active);

    const send = (path, body, keys) => {
        const updateFunc = () => authFetch(path, { method: 'post', body: JSON.stringify(body) })
            .then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(keys, [updateFunc]);
    };
    // The price of a vote is a game number (BASE_VOTES_COST in shared.py).
    const voteCost = universe.votes_cost || props.data.state.game_config?.BASE_VOTES_COST || 0;
    const unusedVotes = props.data.kingdom.votes || 0;
    const affordableVotes = voteCost > 0 ? Math.floor(Math.max(props.data.kingdom.money || 0, 0) / voteCost) : 0;
    const buy = () => {
        if (buyVotes > 0) {
            send('api/votes', { votes: buyVotes }, ['kingdom']);
            setBuyVotes('');
        }
    };
    const cast = (policy, option) => {
        const votes = parseInt(amounts[option], 10) || 0;
        if (votes > 0) {
            send('api/universepolitics/policies', { policy, option, votes }, ['universepolitics', 'kingdom']);
            setAmounts({ ...amounts, [option]: "" });
        }
    };

    const timing = election.open
        ? `Voting is open${closesIn !== null ? `, and closes in ${waitText(closesIn)}` : ""}. Until then the policies below stay in force.`
        : election.start
            ? `The next election opens${opensIn !== null ? ` in ${waitText(opensIn)}` : " soon"}.`
            : "No election is planned.";

    return (
        <div className="universe-politics">
            <ResultToasts title="Votes Result" results={results} setResults={setResults} />
            <p className="vote-rule text-muted">{timing}</p>
            <Panel title="In force">
                {(universe.active || []).length
                    ? (universe.active || []).map((option) => (
                        <p key={option.key} className="universe-active">
                            <strong>{option.policy_name}: {option.name}</strong>. {option.desc}
                            {option.hits_me ? "" : <span className="text-muted"> (not your kingdom)</span>}
                        </p>))
                    : <p className="text-muted">Nothing yet: the first election decides.</p>}
            </Panel>
            <Panel title="Your votes">
                <p>Buy votes to take part. Each costs {voteCost.toLocaleString()} money. You have {unusedVotes.toLocaleString()} to spend.</p>
                <label className="universe-votes-label" htmlFor="buy-votes-input">Votes to buy</label>
                <AmountInput name="votes" id="buy-votes-input" label="Votes to buy" value={buyVotes}
                    onChange={(e) => setBuyVotes(e.target.value)} max={affordableVotes} />
                <Button className="buy-votes-button" variant="primary" onClick={buy} disabled={props.loading.kingdom}>
                    {props.loading.kingdom ? "Loading..." : "Buy"}
                </Button>
                {buyVotes !== "" ? <span className="text-muted"> Votes cost: {((parseInt(buyVotes, 10) || 0) * voteCost).toLocaleString()}</span> : null}
            </Panel>
            {(universe.ballot || []).length ? <h2>{election.open ? "On the ballot" : "On the next ballot"}</h2> : null}
            {(universe.ballot || []).map((policy) => (
                <div className="galaxy-policy" key={policy.key}>
                    <h3>{policy.name}{policy.first_election_only ? <span className="text-muted"> (first election only)</span> : null}</h3>
                    <div className="galaxy-policy-options">
                        {policy.options.map((option) => (
                            <div key={option.key} className="text-box galaxy-policy-card">
                                <span>{option.name}</span>
                                <span>{option.desc}</span>
                                <span className="text-muted">Your votes: {(option.my_votes || 0).toLocaleString()}</span>
                                {election.open
                                    ? <>
                                        <AmountInput name={option.key} id={`votes-${option.key}`} label={`Votes for ${option.name}`}
                                            value={amounts[option.key] || ""} max={unusedVotes}
                                            onChange={(e) => setAmounts({ ...amounts, [option.key]: e.target.value })} />
                                        <Button className="galaxy-policy-button" variant="primary"
                                            disabled={props.loading.universepolitics || !(parseInt(amounts[option.key], 10) > 0)}
                                            onClick={() => cast(policy.key, option.key)}>
                                            Cast votes
                                        </Button>
                                    </>
                                    : null}
                            </div>
                        ))}
                    </div>
                </div>
            ))}
            <HelpButton scrollTarget={"universepolitics"}/>
        </div>
    );
}

export default UniversePolitics;
