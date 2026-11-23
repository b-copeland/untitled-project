import React, { useCallback, useEffect, useState } from "react";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Modal from "react-bootstrap/Modal";
import { adminAuth } from "../auth";
import { Panel, FieldRow, Stats } from "../components/planner";
import { NumberField, SubmitButton } from "../components/forms";
import { ResultToasts, safeJson } from "../components/results";

// The admin's round tools (docs/admin.md): where the round stands, starting a new one, moving its dates, adding bots
// and ending it now. The server checks everything again; the checks here only say no before sending.

const HOUR = 3600 * 1000;

/** A Date as the value of a datetime-local input (local time, to the minute). */
export const toInput = (date) => {
    if (!date || Number.isNaN(date.getTime())) return "";
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

/** A datetime-local value (local time) as the ISO time the server takes, or "" if empty. */
export const fromInput = (value) => (value ? new Date(value).toISOString() : "");

/** A stored ISO time as the admin's local time, or "none". */
export const showTime = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "none");

/** The next whole hour, at least an hour away: a sensible default start that gives players time to sign up. */
const nextStart = (now = new Date()) => {
    const start = new Date(now.getTime() + 2 * HOUR);
    start.setMinutes(0, 0, 0);
    return start;
};

/** Field errors for a new round, as the server would give them; empty when it would be accepted. */
export function newRoundErrors(values, now = new Date(), maxGalaxies = 100) {
    const errors = {};
    const start = values.start ? new Date(values.start) : null;
    const end = values.end ? new Date(values.end) : null;
    const election = values.noElections || !values.election ? null : new Date(values.election);
    if (!start) errors.game_start = "Choose when the round starts";
    if (!end) errors.game_end = "Choose when the round ends";
    else if (end <= now) errors.game_end = "The end must be in the future";
    else if (start && end <= start) errors.game_end = "The end must be after the start";
    if (election && start && end && !(start <= election && election < end)) errors.election_start = "The first election must be during the round";
    const galaxies = Number(values.galaxies);
    if (!Number.isInteger(galaxies) || galaxies < 1 || galaxies > maxGalaxies) errors.num_galaxies = `Between 1 and ${maxGalaxies} galaxies`;
    const clusterSize = Number(values.clusterSize);
    if (!Number.isInteger(clusterSize) || clusterSize < 1) errors.cluster_size = "At least 1 galaxy per cluster";
    const bots = Number(values.bots || 0);
    if (!Number.isInteger(bots) || bots < 0) errors.bots = "A whole number";
    return errors;
}

const PHASES = {
    "not set up": "No round is set up yet",
    "not started": "Waiting for the start",
    running: "Running",
    over: "Over (the game is read only)",
};

function RoundStatus({ round, onReload }) {
    return (
        <Panel title="The round">
            <p className="page-note"><strong>{PHASES[round.phase] || round.phase}</strong>. Times are shown in your time zone.</p>
            <Stats items={[
                { label: "Starts", value: showTime(round.game_start) },
                { label: "Ends", value: showTime(round.game_end) },
                { label: round.election_end ? "Election closes" : "Next election", value: showTime(round.election_end || round.election_start) },
            ]} />
            <Stats items={[
                { label: "Galaxies", value: `${round.galaxies} in ${round.clusters} clusters` },
                { label: "Players", value: round.players },
                { label: "Bots", value: round.bots },
                { label: "Rounds archived", value: round.rounds_archived },
            ]} />
            <div className="form-actions"><Button size="sm" variant="secondary" onClick={onReload}>Refresh</Button></div>
        </Panel>
    );
}

function NewRound({ round, send }) {
    const [values, setValues] = useState(() => {
        const start = nextStart();
        return {
            start: toInput(start),
            end: toInput(new Date(start.getTime() + 7 * 24 * HOUR)),
            election: toInput(new Date(start.getTime() + 2 * 24 * HOUR)),
            noElections: false,
            galaxies: "10",
            clusterSize: String(round.default_cluster_size || 5),
            expected: "",
            bots: "0",
            archive: true,
        };
    });
    const [serverErrors, setServerErrors] = useState({});
    const [confirming, setConfirming] = useState(false);
    const [loading, setLoading] = useState(false);
    const set = (name) => (event) => {
        const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
        setValues((previous) => ({ ...previous, [name]: value }));
        setServerErrors({});
    };
    const errors = { ...newRoundErrors(values, new Date(), round.max_galaxies), ...serverErrors };
    const blocked = Object.values(errors)[0] || null;
    const galaxies = Number(values.galaxies) || 0;
    const clusterSize = Number(values.clusterSize) || 1;
    const clusters = Math.ceil(galaxies / clusterSize);
    const bots = Number(values.bots) || 0;
    const expected = Number(values.expected) || 0;
    const perGalaxy = galaxies && (expected + bots) ? ((expected + bots) / galaxies).toFixed(1) : null;
    const lengthDays = values.start && values.end ? (new Date(values.end) - new Date(values.start)) / (24 * HOUR) : 0;

    const start = () => {
        setLoading(true);
        const body = {
            game_start: fromInput(values.start),
            game_end: fromInput(values.end),
            // Empty: the first election opens a set time after the start. "" asks for none.
            election_start: values.noElections ? "" : (values.election ? fromInput(values.election) : null),
            num_galaxies: galaxies,
            cluster_size: clusterSize,
            archive: values.archive,
        };
        send("api/admin/newround", body).then((result) => {
            if (result.errors) setServerErrors(result.errors);
            if (result.status === "success" && bots > 0) {
                return send("api/admin/bots", { total: bots });
            }
            return result;
        }).finally(() => { setLoading(false); setConfirming(false); });
    };

    const field = (label, name, input, hint) => (
        <FieldRow label={label} hint={hint} htmlFor={`newround-${name}`}>
            {input}
            {errors[name] ? <div className="invalid-feedback d-block">{errors[name]}</div> : null}
        </FieldRow>
    );
    const time = (name, key) => (
        <Form.Control type="datetime-local" id={`newround-${name}`} value={values[key]} onChange={set(key)} isInvalid={Boolean(errors[name])} />
    );

    return (
        <Panel title="Start a new round" hint="Deletes every kingdom, galaxy, empire and their news. Accounts and archived rounds stay.">
            {field("Starts", "game_start", time("game_start", "start"), "Players can make kingdoms before the start")}
            {field("Ends", "game_end", time("game_end", "end"), lengthDays > 0 ? `${lengthDays.toFixed(1)} days long` : null)}
            <FieldRow label="First election" htmlFor="newround-election_start"
                hint={`Empty: ${round.first_election_hours ?? "some"} hours after the start. Each lasts ${round.election_hours} hours; the next opens ${round.election_every_hours} hours after the last one opened`}>
                <Form.Control type="datetime-local" id="newround-election_start" value={values.election} onChange={set("election")}
                    disabled={values.noElections} isInvalid={Boolean(errors.election_start)} />
                {errors.election_start ? <div className="invalid-feedback d-block">{errors.election_start}</div> : null}
                <Form.Check type="checkbox" id="newround-no-elections" label="No elections" checked={values.noElections} onChange={set("noElections")} />
            </FieldRow>
            {field("Galaxies", "num_galaxies",
                <NumberField name="galaxies" id="newround-num_galaxies" value={values.galaxies} onChange={set("galaxies")} error={null} />,
                "Fixed for the round: new kingdoms join the galaxy with the fewest")}
            {field("Galaxies per cluster", "cluster_size",
                <NumberField name="clusterSize" id="newround-cluster_size" value={values.clusterSize} onChange={set("clusterSize")} error={null} />,
                galaxies ? `${clusters} cluster${clusters === 1 ? "" : "s"}, dealt in order` : null)}
            {field("Players expected", "expected",
                <NumberField name="expected" id="newround-expected" value={values.expected} onChange={set("expected")} placeholder="optional" />,
                perGalaxy ? `About ${perGalaxy} kingdoms per galaxy, bots included` : "Only to work out the galaxy size")}
            {field("Bots", "bots",
                <NumberField name="bots" id="newround-bots" value={values.bots} onChange={set("bots")} error={null} />,
                "Added straight after, in the default mix of playstyles")}
            {round.phase === "running" ? (
                <Form.Check type="checkbox" id="newround-archive" className="mb-2" checked={values.archive} onChange={set("archive")}
                    label="Archive the running round first (it has not finished)" />
            ) : null}
            <div className="form-actions">
                <SubmitButton variant="warning" blocked={blocked} onClick={() => setConfirming(true)}>Start new round</SubmitButton>
            </div>
            <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                <Modal.Header closeButton><Modal.Title>Start a new round?</Modal.Title></Modal.Header>
                <Modal.Body>
                    <p>Every kingdom, galaxy and empire of the current round is deleted{round.kingdoms ? ` (${round.kingdoms} kingdoms)` : ""}, and every player has to sign in again.</p>
                    <p>The new round: {galaxies} galaxies in {clusters} clusters, from {showTime(fromInput(values.start))} to {showTime(fromInput(values.end))}
                        {values.noElections ? ", with no elections" : `, first election ${showTime(fromInput(values.election))}`}{bots ? `, then ${bots} bots` : ""}.</p>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                    <SubmitButton variant="warning" loading={loading} onClick={start}>Delete it and start</SubmitButton>
                </Modal.Footer>
            </Modal>
        </Panel>
    );
}

function ChangeDates({ round, send }) {
    const notStarted = round.phase === "not started";
    const [values, setValues] = useState({
        start: toInput(new Date(round.game_start)),
        end: toInput(new Date(round.game_end)),
        election: round.election_start ? toInput(new Date(round.election_start)) : "",
    });
    const [errors, setErrors] = useState({});
    const set = (name) => (event) => { setValues({ ...values, [name]: event.target.value }); setErrors({}); };
    const electionOpen = Boolean(round.election_end);

    const save = () => {
        const body = { game_end: fromInput(values.end) };
        if (notStarted) body.game_start = fromInput(values.start);
        if (!electionOpen) body.election_start = fromInput(values.election);
        send("api/admin/round", body).then((result) => setErrors(result.errors || {}));
    };
    const row = (label, name, key, disabled, hint) => (
        <FieldRow label={label} hint={hint} htmlFor={`round-${name}`}>
            <Form.Control type="datetime-local" id={`round-${name}`} value={values[key]} onChange={set(key)} disabled={disabled} isInvalid={Boolean(errors[name])} />
            {errors[name] ? <div className="invalid-feedback d-block">{errors[name]}</div> : null}
        </FieldRow>
    );
    return (
        <Panel title="Change the dates">
            {row("Starts", "game_start", "start", !notStarted, notStarted ? null : "Started: it can not move")}
            {row("Ends", "game_end", "end", false)}
            {row("Next election", "election_start", "election", electionOpen, electionOpen ? "An election is open" : "Empty for no more elections")}
            {errors.round ? <p className="text-danger">{errors.round}</p> : null}
            <div className="form-actions"><SubmitButton blocked={null} onClick={save}>Save dates</SubmitButton></div>
        </Panel>
    );
}

function AddBots({ round, send }) {
    const [bots, setBots] = useState("");
    const number = Number(bots);
    const blocked = !bots ? "How many?" : (!Number.isInteger(number) || number < 1 ? "A whole number"
        : number > round.max_bots ? `At most ${round.max_bots} at a time` : null);
    return (
        <Panel title="Add bots" hint="Each joins the galaxy with the fewest kingdoms, in the default mix of playstyles.">
            <FieldRow label="Bots" htmlFor="addbots-input">
                <NumberField name="bots" id="addbots-input" value={bots} onChange={(e) => setBots(e.target.value)} placeholder="0" />
            </FieldRow>
            <div className="form-actions">
                <SubmitButton blocked={blocked} onClick={() => send("api/admin/bots", { total: number }).then(() => setBots(""))}>Add bots</SubmitButton>
            </div>
        </Panel>
    );
}

function EndNow({ send }) {
    const [confirming, setConfirming] = useState(false);
    return (
        <Panel title="End the round now" className="warning-zone" hint="Archives it and makes the game read only, as when its end time passes.">
            <div className="form-actions"><Button variant="warning" onClick={() => setConfirming(true)}>End the round</Button></div>
            <Modal show={confirming} onHide={() => setConfirming(false)} animation={false}>
                <Modal.Header closeButton><Modal.Title>End the round now?</Modal.Title></Modal.Header>
                <Modal.Body>Nobody can act after this. It can not be undone, only followed by a new round.</Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
                    <Button variant="warning" onClick={() => send("api/admin/endround").then(() => setConfirming(false))}>End it</Button>
                </Modal.Footer>
            </Modal>
        </Panel>
    );
}

function AdminRound({ onChange = () => {} }) {
    const [round, setRound] = useState(null);
    const [error, setError] = useState("");
    const [results, setResults] = useState([]);

    const load = useCallback(() => {
        adminAuth.authFetch("api/admin/round").then(safeJson).then((r) => {
            if (r.phase) { setRound(r); setError(""); } else { setError(r.message || "Could not load the round"); }
        }).catch(() => setError("Could not load the round"));
    }, []);
    useEffect(() => { load(); }, [load]);

    /** POST ``body`` to ``url``, show the result, reload the round, and hand the result back. */
    const send = useCallback((url, body) => adminAuth.authFetch(url, {
        method: "POST",
        body: body === undefined ? undefined : JSON.stringify(body),
    }).then(safeJson).then((result) => {
        setResults((previous) => previous.concat(result));
        load();
        onChange();
        return result;
    }), [load, onChange]);

    if (error) return <p role="alert">{error}</p>;
    if (!round) return <p>Loading the round…</p>;
    const live = round.phase === "running" || round.phase === "not started";
    return (
        <div className="admin-round">
            <div className="panel-grid">
                <RoundStatus round={round} onReload={load} />
                {/* keyed on the dates, so the form starts from the stored ones after each change */}
                {live ? <ChangeDates key={`${round.game_start}${round.game_end}${round.election_start}${round.election_end}`} round={round} send={send} /> : null}
            </div>
            <div className="panel-grid">
                <NewRound round={round} send={send} />
                {live ? <AddBots round={round} send={send} /> : null}
            </div>
            {round.phase === "running" ? <EndNow send={send} /> : null}
            <ResultToasts title="Admin" results={results} setResults={setResults} />
        </div>
    );
}

export default AdminRound;
