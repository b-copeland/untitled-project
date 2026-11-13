import React, { useCallback, useEffect, useState } from "react";
import Alert from "react-bootstrap/Alert";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Modal from "react-bootstrap/Modal";
import { authFetch } from "../auth";
import { AmountInput, SubmitButton, useFormValues } from "../components/forms";
import HelpButton from "../components/helpbutton";
import { FieldRow, Panel, Stats } from "../components/planner";
import { safeJson } from "../components/results";
import { checkChoices, kingdomStats } from "../kingdomstats";
import { raceDescriptions } from "../races";
import "./createkingdom.css";

/*
 * Where a new player makes their kingdom: a name, a way to play, then a look at the result. The way to play is one of
 * the quick starts (the same four archetypes the bots use: each is a race, a starting kingdom and a plan for the auto
 * builder) or "Custom", where the player spends the starting unit points and stars themselves. Nothing is made until the
 * last button, and then it is one request.
 */

const MAX_NAME = 24;

const UNITS = [
    ["drones", "Drones", "Spy on other kingdoms and rob primitives. Factories make more over time."],
    ["recruits", "Recruits", "Raw people. Military units are trained from them later."],
    ["attack", "Attackers", "Offense only. The cheapest way to hit hard."],
    ["defense", "Defenders", "Defense only. Keeps what you have."],
    ["flex", "Flexers", "Offense and defense in one unit, for more points."],
    ["engineers", "Engineers", "Work on projects. Workshops are where they live."],
];

const STRUCTURES = [
    ["homes", "Homes", "Hold your population, which pays income."],
    ["mines", "Mines", "Make money."],
    ["fuel_plants", "Fuel Plants", "Make the fuel your people and units burn."],
    ["hangars", "Hangars", "Hold your military. Units beyond their room can't be kept."],
    ["drone_factories", "Drone Factories", "Build drones over time."],
    ["missile_silos", "Missile Silos", "Hold missiles."],
    ["workshops", "Workshops", "House engineers."],
];

const SPENDING_WORDS = { settle: "settling new stars", structures: "building structures", military: "training military", engineers: "engineers and projects" };

const percent = (fraction) => `${Math.round(fraction * 100)}%`;

/** "50% on settling new stars, 30% on building structures", from a preset's auto spending split. */
const describeSpending = (split) => Object.entries(split)
    .filter(([, share]) => share > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([what, share]) => `${percent(share)} on ${SPENDING_WORDS[what] || what}`)
    .join(", ");

/** What the auto builder of a preset does, for the question about switching it on. */
function autoBuilderSummary(preset) {
    const lines = [`spends your income: ${describeSpending(preset.autoSpending)}`];
    if (preset.autoAttack) lines.push("sends units against primitives (neutral stars) whenever your generals are free");
    if (preset.autoRob) lines.push("robs primitives with your drones on a timer");
    return lines;
}

function RaceNotes({ race, descriptions }) {
    const notes = descriptions[race];
    if (!notes) return null;
    return (
        <ul className="race-notes">
            {notes.pros.map((line) => <li key={line} className="race-pro">{line}</li>)}
            {notes.cons.map((line) => <li key={line} className="race-con">{line}</li>)}
        </ul>
    );
}

function KingdomStats({ stats }) {
    const n = (value) => Math.floor(value).toLocaleString();
    return (
        <Stats items={[
            { label: "Offense", value: n(stats.offense) },
            { label: "Defense", value: n(stats.defense) },
            { label: "Population", value: n(stats.population) },
            { label: "Income", value: n(stats.income) },
            { label: "Fuel made", value: n(stats.fuelProduction) },
            { label: "Fuel used", value: n(stats.fuelUsage), tone: stats.fuelUsage > stats.fuelProduction ? "bad" : undefined },
            { label: "Hangar room", value: `${n(stats.hangarUsed)} / ${n(stats.hangarCapacity)}`, tone: stats.hangarUsed > stats.hangarCapacity ? "bad" : undefined },
            { label: "Drones made", value: n(stats.dronesPerTick) },
            { label: "Engineers housed", value: `${n(stats.engineers)} / ${n(stats.workshopCapacity)}`, tone: stats.engineers > stats.workshopCapacity ? "bad" : undefined },
        ]} />
    );
}

function StepsBar({ steps, current }) {
    const at = steps.findIndex((step) => step.id === current);
    return (
        <ol className="creator-steps" aria-label="Steps">
            {steps.map((step, index) => (
                <li key={step.id} className={index === at ? "current" : index < at ? "done" : ""} aria-current={index === at ? "step" : undefined}>
                    <span className="creator-step-number">{index + 1}</span> {step.label}
                </li>
            ))}
        </ol>
    );
}

function CreateKingdom(props) {
    const { kingdomid, kingdoms = {}, state, updateData } = props;
    const [creatorData, setCreatorData] = useState(null);
    const [loadFailed, setLoadFailed] = useState(false);
    const [name, setName] = useState("");
    const [stepId, setStepId] = useState(null);
    const [choice, setChoice] = useState(null); // a preset's key, "custom", or nothing yet
    const [seedFrom, setSeedFrom] = useState(null); // the preset whose numbers the custom form started from
    const [race, setRace] = useState("");
    const units = useFormValues({});
    const structures = useFormValues({});
    const [askAuto, setAskAuto] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    const load = useCallback(() => {
        setLoadFailed(false);
        authFetch("api/createkingdomdata")
            .then((r) => r.json())
            .then((data) => (data.presets ? setCreatorData(data) : setLoadFailed(true)))
            .catch(() => setLoadFailed(true));
    }, []);
    useEffect(load, [load]);

    if (loadFailed) {
        return (
            <div className="creator">
                <Alert variant="danger">Could not load the kingdom creator.</Alert>
                <Button onClick={load}>Try again</Button>
            </div>
        );
    }
    if (kingdomid.kd_id === undefined || creatorData === null || Object.keys(state).length === 0) {
        return <h2>Loading...</h2>;
    }

    // A kingdom that was made but never set up (Reset Kingdom, or the old two-step flow) keeps its name.
    const hasKingdom = Boolean(kingdomid.kd_id);
    const steps = [
        ...(hasKingdom ? [] : [{ id: "name", label: "Name" }]),
        { id: "style", label: "How you play" },
        { id: "confirm", label: "Create" },
    ];
    const current = steps.some((step) => step.id === stepId) ? stepId : steps[0].id;
    const goTo = (id) => { setError(""); setStepId(id); };
    const next = () => goTo(steps[steps.findIndex((step) => step.id === current) + 1].id);
    const back = () => goTo(steps[steps.findIndex((step) => step.id === current) - 1].id);

    const kingdomName = hasKingdom ? (kingdoms[kingdomid.kd_id] || "your kingdom") : name.trim();
    const descriptions = raceDescriptions(state.game_config);
    const presets = creatorData.presets;
    const preset = presets.find((candidate) => candidate.key === choice);

    // The name step.
    const taken = Object.values(kingdoms).some((existing) => String(existing).toLowerCase() === name.trim().toLowerCase());
    const nameProblem = name.trim() === "" ? "Choose a name"
        : name.trim().length > MAX_NAME ? `Names are at most ${MAX_NAME} characters`
        : taken ? "Another kingdom already has that name"
        : null;

    // The style step.
    const startCustom = (from) => {
        const source = from || presets[0];
        setSeedFrom(source.key);
        setRace(source.race);
        Object.entries(source.unitsChoices).forEach(([unit, amount]) => units.set(unit, String(amount)));
        UNITS.forEach(([unit]) => { if (!(unit in source.unitsChoices)) units.set(unit, ""); });
        STRUCTURES.forEach(([structure]) => structures.set(structure, String(source.structuresChoices[structure] || "")));
    };
    const choose = (key) => {
        if (key === "custom" && choice !== "custom") startCustom(preset);
        setChoice(key);
    };
    const check = choice === "custom"
        ? checkChoices({ units: units.values, structures: structures.values, race }, creatorData)
        : { pointsLeft: 0, starsLeft: 0, blocked: preset ? null : "Choose how you want to play" };
    const chosenUnits = preset ? preset.unitsChoices : units.values;
    const chosenStructures = preset ? preset.structuresChoices : structures.values;
    const chosenRace = preset ? preset.race : race;

    const submit = async (autoBuilder) => {
        setAskAuto(false);
        setSubmitting(true);
        setError("");
        const body = preset
            ? { preset: preset.key, autoBuilder }
            : { race, unitsChoices: units.values, structuresChoices: structures.values };
        if (!hasKingdom) body.kdName = name.trim();
        try {
            const response = await authFetch("api/createkingdom", { method: "post", body: JSON.stringify(body) });
            const result = await safeJson(response);
            if (response.ok) {
                // The page is replaced once the kingdom shows as created; the rest of the game's data follows (gameData.js).
                await updateData(["kingdomid"]);
            } else {
                setError(result.message || "The kingdom could not be created");
                if (result.field === "name") setStepId("name");
            }
        } catch (err) {
            setError("Could not reach the server, try again");
        } finally {
            setSubmitting(false);
        }
    };
    const onCreate = () => (preset ? setAskAuto(true) : submit(false));

    const unitCost = creatorData.selection_points;
    const unitMax = (unit) => (Number(units.values[unit]) || 0) + Math.max(Math.floor(check.pointsLeft / unitCost[unit]), 0);
    const structureMax = (structure) => (Number(structures.values[structure]) || 0) + Math.max(check.starsLeft, 0);

    return (
        <div className="creator">
            <h2>Create your kingdom</h2>
            <StepsBar steps={steps} current={current} />
            {error ? <Alert variant="danger" className="py-2">{error}</Alert> : null}

            {current === "name" ? (
                <Panel title="Name your kingdom" hint="Other players see this name. Rounds last days to weeks, so a good plan counts for more than constant clicking.">
                    <Form onSubmit={(event) => { event.preventDefault(); if (!nameProblem) next(); }}>
                        <Form.Group controlId="kd-name-input">
                            <Form.Label>Kingdom name</Form.Label>
                            <Form.Control value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" autoFocus
                                maxLength={MAX_NAME + 10} isInvalid={name !== "" && Boolean(nameProblem)} />
                            <Form.Control.Feedback type="invalid">{nameProblem}</Form.Control.Feedback>
                        </Form.Group>
                        <div className="creator-actions">
                            <SubmitButton blocked={nameProblem} onClick={(event) => { event.preventDefault(); next(); }}>Next</SubmitButton>
                        </div>
                    </Form>
                </Panel>
            ) : null}

            {current === "style" ? (
                <>
                    <Panel title="How do you want to play?"
                        hint="Pick the closest to your style. Each is a race and a starting kingdom, and comes with a ready-made plan for the auto builder that you can switch on or leave off. You can change anything later.">
                        <div className="preset-cards" role="radiogroup" aria-label="Quick starts">
                            {presets.map((candidate) => (
                                <button key={candidate.key} type="button" role="radio" aria-checked={choice === candidate.key}
                                    className={"preset-card" + (choice === candidate.key ? " selected" : "")} onClick={() => choose(candidate.key)}>
                                    <strong>{candidate.label}</strong>
                                    <span className="preset-race">{candidate.race}</span>
                                    <span>{candidate.description}</span>
                                </button>
                            ))}
                            <button type="button" role="radio" aria-checked={choice === "custom"}
                                className={"preset-card" + (choice === "custom" ? " selected" : "")} onClick={() => choose("custom")}>
                                <strong>Custom</strong>
                                <span className="preset-race">Your choice</span>
                                <span>Spend the starting points and stars yourself, and pick your own race.</span>
                            </button>
                        </div>
                    </Panel>

                    {preset ? (
                        <Panel title={`${preset.label}: ${preset.race}`}>
                            <RaceNotes race={preset.race} descriptions={descriptions} />
                            <KingdomStats stats={kingdomStats(state, preset.unitsChoices, preset.structuresChoices)} />
                        </Panel>
                    ) : null}

                    {choice === "custom" ? (
                        <>
                            <Panel title="Race" hint="Races give a bonus and a drawback for the whole round.">
                                <Form.Select aria-label="Race" value={race} onChange={(event) => setRace(event.target.value)}>
                                    <option value="" disabled>Choose a race</option>
                                    {state.races.map((option) => <option key={option} value={option}>{option}</option>)}
                                </Form.Select>
                                <RaceNotes race={race} descriptions={descriptions} />
                                <div className="creator-seed">
                                    Start from a quick start:{" "}
                                    {presets.map((candidate) => (
                                        <Button key={candidate.key} variant={seedFrom === candidate.key ? "secondary" : "outline-secondary"} size="sm"
                                            onClick={() => startCustom(candidate)}>{candidate.label}</Button>
                                    ))}
                                </div>
                            </Panel>
                            <div className="creator-grid">
                                <Panel title="Units" hint={`${check.pointsLeft.toLocaleString()} of ${creatorData.total_points.toLocaleString()} points left to spend.`}>
                                    {UNITS.map(([unit, label, hint]) => (
                                        <FieldRow key={unit} label={label} hint={`${unitCost[unit]} point${unitCost[unit] === 1 ? "" : "s"} each. ${hint}`} htmlFor={`${unit}-input`}>
                                            <AmountInput box name={unit} label={label} value={units.values[unit]} onChange={units.onChange}
                                                max={unitMax(unit)} soloMax={Math.floor(creatorData.total_points / unitCost[unit])} />
                                        </FieldRow>
                                    ))}
                                </Panel>
                                <Panel title="Structures" hint={`${check.starsLeft} of ${creatorData.total_stars} stars left to build on.`}>
                                    {STRUCTURES.map(([structure, label, hint]) => (
                                        <FieldRow key={structure} label={label} hint={hint} htmlFor={`${structure}-input`}>
                                            <AmountInput box name={structure} label={label} value={structures.values[structure]} onChange={structures.onChange}
                                                max={structureMax(structure)} soloMax={creatorData.total_stars} />
                                        </FieldRow>
                                    ))}
                                </Panel>
                            </div>
                            <Panel title="What this makes">
                                <KingdomStats stats={kingdomStats(state, units.values, structures.values)} />
                            </Panel>
                        </>
                    ) : null}

                    <div className="creator-actions">
                        {steps.length > 2 ? <Button variant="outline-secondary" onClick={back}>Back</Button> : null}
                        <SubmitButton blocked={check.blocked} onClick={next}>Next</SubmitButton>
                    </div>
                </>
            ) : null}

            {current === "confirm" ? (
                <>
                    <Panel title="Ready?" hint={hasKingdom ? undefined : "You will be placed in the galaxy with the fewest kingdoms, with other players to work with."}>
                        <Stats items={[
                            { label: "Kingdom", value: kingdomName },
                            { label: "Playstyle", value: preset ? preset.label : "Custom" },
                            { label: "Race", value: chosenRace },
                        ]} />
                        <RaceNotes race={chosenRace} descriptions={descriptions} />
                        <KingdomStats stats={kingdomStats(state, chosenUnits, chosenStructures)} />
                    </Panel>
                    <div className="creator-actions">
                        <Button variant="outline-secondary" onClick={back} disabled={submitting}>Back</Button>
                        <SubmitButton loading={submitting} onClick={onCreate}>Create kingdom</SubmitButton>
                    </div>
                </>
            ) : null}

            <Modal show={askAuto} onHide={() => setAskAuto(false)} centered>
                <Modal.Header closeButton><Modal.Title>Switch on the auto builder?</Modal.Title></Modal.Header>
                <Modal.Body>
                    {preset ? (
                        <>
                            <p>The {preset.label} plan is saved with your kingdom either way. With the auto builder on, it:</p>
                            <ul>{autoBuilderSummary(preset).map((line) => <li key={line}>{line}</li>)}</ul>
                            <p>
                                That keeps your kingdom growing while you are away, but it spends and acts without asking. Left off, nothing
                                happens until you decide. You can change your mind at any time: auto spending on the Status page, and
                                {preset.autoAttack || preset.autoRob ? " auto attack and robbing on the Primitives page" : " the rest of the plan on the Build pages"}.
                            </p>
                        </>
                    ) : null}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="outline-secondary" onClick={() => submit(false)}>Keep it off</Button>
                    <Button variant="primary" onClick={() => submit(true)}>Switch it on</Button>
                </Modal.Footer>
            </Modal>
            <HelpButton scrollTarget={"createkingdom"} />
        </div>
    );
}

export default CreateKingdom;
