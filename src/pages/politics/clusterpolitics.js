import React, { useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Form from 'react-bootstrap/Form';
import ProgressBar from 'react-bootstrap/ProgressBar';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import { authFetch } from "../../auth";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { GameTable } from "../../components/gametable";
import { SubmitButton } from "../../components/forms";
import { Panel, Stats } from "../../components/planner";
import { ResultToasts, safeJson } from "../../components/results";
import "./clusterpolitics.css";

/** 0.0123 -> "1.23%" */
const percent = (fraction, digits = 2) => `${((fraction || 0) * 100).toFixed(digits)}%`;

/** The server works per epoch; players read real time. Turns a per-epoch figure into a per-hour one (null if unknown). */
export const perHour = (perEpoch, epochSeconds) => (epochSeconds ? ((perEpoch || 0) * 3600) / epochSeconds : null);

/** A change per hour, with its sign: "+0.07%", "-0.05%", "Holding", or "--" when the rate is not known. */
const change = (fraction) => {
    if (fraction === null) return "--";
    if (!fraction || Math.abs(fraction) < 1e-9) return "Holding";
    return `${fraction > 0 ? "+" : "-"}${percent(Math.abs(fraction), 3)}`;
};

/** A wait in real time, rounded up to the minute: "2 h 5 min", "40 min". */
export function waitText(milliseconds) {
    const minutes = Math.max(1, Math.ceil(milliseconds / 60000));
    const hours = Math.floor(minutes / 60);
    return [hours ? `${hours} h` : "", minutes % 60 ? `${minutes % 60} min` : ""].filter(Boolean).join(" ");
}

/** How long until ``unlocksAt`` (an ISO time or null), re-read every 30 seconds; null once it has passed. */
export function useWait(unlocksAt) {
    const [now, setNow] = useState(Date.now());
    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 30000);
        return () => clearInterval(timer);
    }, []);
    const left = unlocksAt ? Date.parse(unlocksAt) - now : 0;
    return left > 0 ? left : null;
}

/** The benefits in the game's order (the server sends ``order``, since the object's keys arrive sorted). */
export const benefitsOf = (cluster) => (cluster.order || Object.keys(cluster.benefits || {}))
    .filter((key) => cluster.benefits?.[key])
    .map((key) => ({ key, ...cluster.benefits[key] }));

const empireName = (data, empireId) => (empireId != null ? data.empires?.[empireId]?.name || `Empire ${empireId}` : "None");

function BenefitsTable({ cluster, epochSeconds }) {
    return (
        <GameTable
            className="game-table cluster-table"
            rows={benefitsOf(cluster)}
            columns={[
                {
                    header: "Benefit", align: "left",
                    cell: (row) => <><strong>{row.name}</strong><br /><small className="text-muted">{row.desc}</small></>,
                },
                {
                    header: "Now", align: "left", className: "cluster-level",
                    cell: (row) => (
                        <>
                            <span>{percent(row.value)} of {percent(row.max, 0)}</span>
                            <ProgressBar now={(row.level || 0) * 100} aria-label={`${row.name} at ${percent(row.level, 0)} of its max`} />
                        </>
                    ),
                },
                { header: "Per hour", cell: (row) => change(perHour(row.rate_per_epoch, epochSeconds)) },
                { header: "Votes", cell: (row) => row.votes },
            ]}
        />
    );
}

function GalaxiesTable({ cluster, data }) {
    const names = Object.fromEntries(benefitsOf(cluster).map((benefit) => [benefit.key, benefit.name]));
    return (
        <GameTable
            className="game-table cluster-table"
            rows={(cluster.galaxies || []).map((galaxy) => ({ ...galaxy, key: galaxy.id }))}
            rowClassName={(row) => (row.id === cluster.galaxy ? "cluster-row-mine" : undefined)}
            columns={[
                { header: "Galaxy", align: "left", cell: (row) => (row.id === cluster.galaxy ? `${row.id} (yours)` : row.id) },
                { header: "Kingdoms", cell: (row) => row.kingdoms },
                { header: "Empire", align: "left", cell: (row) => empireName(data, row.empire) },
                { header: "Votes for", align: "left", cell: (row) => names[row.vote] || "No vote" },
            ]}
        />
    );
}

/** Whether this kingdom leads its galaxy, and so casts its vote. The server checks it again when the vote is sent. */
export const leadsGalaxy = (data) => {
    const leader = data.galaxypolitics?.leader;
    return Boolean(leader) && String(leader) === String(data.kingdomid?.kd_id);
};

function VoteForm({ cluster, isLeader, loading, send }) {
    const mine = (cluster.galaxies || []).find((galaxy) => galaxy.id === cluster.galaxy) || {};
    const [choice, setChoice] = useState(mine.vote || "");
    const wait = useWait(cluster.vote_unlocks_at);
    const locked = wait !== null ? `Your galaxy changed its vote recently. It can change again in ${waitText(wait)}.` : null;
    const rule = cluster.vote_cooldown_hours ? `Once changed, a galaxy's vote stays for ${cluster.vote_cooldown_hours} hours.` : null;
    if (!isLeader) {
        return (
            <>
                <p className="mb-0">Only your galaxy leader casts your galaxy's vote. Vote for a leader on the Galaxy page under Politics.</p>
                {locked ? <p className="planner-hint-line">{locked}</p> : null}
            </>
        );
    }
    const unchanged = (choice || null) === (mine.vote || null);
    return (
        <Form className="cluster-vote-form" onSubmit={(event) => { event.preventDefault(); send(choice || null); }}>
            <Form.Label htmlFor="cluster-vote-select">Your galaxy votes for</Form.Label>
            <Form.Select id="cluster-vote-select" value={choice} disabled={Boolean(locked)} onChange={(event) => setChoice(event.target.value)}>
                <option value="">No vote</option>
                {benefitsOf(cluster).map((benefit) => <option key={benefit.key} value={benefit.key}>{benefit.name}</option>)}
            </Form.Select>
            <SubmitButton loading={loading} blocked={locked || (unchanged ? "That is already your galaxy's vote" : null)}>
                {choice ? "Vote" : "Withdraw vote"}
            </SubmitButton>
            {locked ? <p className="planner-why">{locked}</p> : rule ? <p className="planner-hint-line">{rule}</p> : null}
        </Form>
    );
}

function ClusterPolitics(props) {
    const [results, setResults] = useState([]);
    const cluster = props.data.cluster || {};
    const epochSeconds = props.data.state?.game_config?.BASE_EPOCH_SECONDS;
    if (props.loading.cluster && !cluster.benefits) {
        return <h2>Loading...</h2>;
    }
    if (!cluster.benefits) {
        return (
            <>
                <Header data={props.data} />
                <p className="cluster-politics">{cluster.message || "Your cluster could not be loaded."}</p>
            </>
        );
    }
    const send = (benefit) => {
        const vote = () => authFetch("api/cluster/vote", { method: "POST", body: JSON.stringify({ benefit }) })
            .then(safeJson).then((result) => setResults((previous) => previous.concat(result)));
        props.updateData(["cluster"], [vote]);
    };
    const mine = (cluster.galaxies || []).find((galaxy) => galaxy.id === cluster.galaxy) || {};
    const myVote = benefitsOf(cluster).find((benefit) => benefit.key === mine.vote);
    return (
        <>
            <Header data={props.data} />
            <div className="cluster-politics">
                <ResultToasts title="Cluster" results={results} setResults={setResults} />
                <Stats items={[
                    { label: "Cluster", value: cluster.cluster },
                    { label: "Galaxies", value: (cluster.galaxies || []).length },
                    { label: "Your galaxy votes for", value: myVote ? myVote.name : "Nothing" },
                ]} />
                <Tabs id="cluster-tabs" defaultActiveKey="benefits" variant="tabs">
                    <Tab eventKey="benefits" title="Benefits">
                        <Panel title="What the cluster has built up"
                            hint={epochSeconds
                                ? `Every kingdom in the cluster gets these. A vote adds ${percent(perHour(cluster.vote_gain_per_epoch, epochSeconds), 2)} of a benefit's max each hour, less as it gets higher, and every benefit loses ${percent(perHour(cluster.decay_per_epoch, epochSeconds), 2)} of its max each hour.`
                                : "Every kingdom in the cluster gets these."}>
                            <BenefitsTable cluster={cluster} epochSeconds={epochSeconds} />
                        </Panel>
                        <Panel title="Your galaxy's vote" className="cluster-form-panel">
                            <VoteForm key={mine.vote || ""} cluster={cluster} isLeader={leadsGalaxy(props.data)}
                                loading={props.loading.cluster} send={send} />
                        </Panel>
                    </Tab>
                    <Tab eventKey="galaxies" title={`Galaxies (${(cluster.galaxies || []).length})`}>
                        <Panel title="Galaxies in your cluster">
                            <GalaxiesTable cluster={cluster} data={props.data} />
                        </Panel>
                    </Tab>
                </Tabs>
            </div>
            <HelpButton scrollTarget={"clusterpolitics"} />
        </>
    );
}

export default ClusterPolitics;
