import React, { useState } from "react";
import { authFetch } from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import "./missiles.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { GameTable } from "../../components/gametable";
import { AmountInput, SubmitButton, useFormValues } from "../../components/forms";
import { anyFilled, checkCount, firstError } from "../../validation";

// Star and galaxy busters have to be researched as projects before they can be built.
const MISSILES = [
    { key: "planet_busters", label: "Planet Buster", project: null },
    { key: "star_busters", label: "Star Buster", project: "star_busters", projectName: "Star Busters" },
    { key: "galaxy_busters", label: "Galaxy Buster", project: "galaxy_busters", projectName: "Galaxy Busters" },
];

const noneYet = Object.fromEntries(MISSILES.map(({ key }) => [key, ""]));

const toHHMMSS = (secs) => {
    const total = parseInt(secs, 10);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor(total / 60) % 60;
    const seconds = total % 60;
    return [hours, minutes, seconds]
        .map((v) => (v < 10 ? "0" + v : v))
        .filter((v, i) => v !== "00" || i > 0)
        .join(":");
};

function Missiles(props) {
    const [results, setResults] = useState([]);
    const form = useFormValues(noneYet);

    if (Object.keys(props.data.kingdom).length === 0 || Object.keys(props.data.missiles).length === 0) {
        return null;
    }
    const kingdom = props.data.kingdom;
    const info = props.data.missiles;
    const locked = ({ project }) => project !== null && kingdom.completed_projects.indexOf(project) < 0;

    const costOf = (field) => MISSILES.reduce(
        (total, { key }) => total + (parseInt(form.values[key], 10) || 0) * info.desc[key][field] * info.cost_modifier, 0);
    const cost = costOf("cost");
    const fuelCost = costOf("fuel_cost");

    // Room for more of a kind: what the silos hold, less what is built and what is being built.
    const room = ({ key }) => Math.max((info.capacity || 0) - (info.current[key] || 0) - (info.building[key] || 0), 0);
    const fieldErrors = Object.fromEntries(MISSILES.map((missile) => [missile.key, checkCount(form.values[missile.key], { max: room(missile), noun: "missiles" })]));
    const moneyError = cost > kingdom.money ? `Costs ${Math.floor(cost).toLocaleString()} money, you have ${Math.floor(kingdom.money).toLocaleString()}` : null;
    const fuelError = fuelCost > kingdom.fuel ? `Needs ${Math.floor(fuelCost).toLocaleString()} fuel, you have ${Math.floor(kingdom.fuel).toLocaleString()}` : null;
    // The most of one kind: the room in the silos, and what the money and fuel still cover after the other kinds.
    const maxFor = (missile) => {
        const mine = parseInt(form.values[missile.key], 10) || 0;
        const left = (field, have) => {
            const each = info.desc[missile.key][field] * info.cost_modifier;
            return each > 0 ? Math.floor((have - (costOf(field) - mine * each)) / each) : Infinity;
        };
        return Math.max(Math.min(room(missile), left("cost", kingdom.money), left("fuel_cost", kingdom.fuel)), 0);
    };
    const soloFor = (missile) => {
        const each = (field) => info.desc[missile.key][field] * info.cost_modifier;
        const afford = (field, have) => (each(field) > 0 ? Math.floor(have / each(field)) : Infinity);
        return Math.max(Math.min(room(missile), afford("cost", kingdom.money), afford("fuel_cost", kingdom.fuel)), 0);
    };
    const blocked = firstError(fieldErrors, moneyError, fuelError) || (anyFilled(form.values) ? null : "Enter how many of each to build");

    const onSubmitClick = () => {
        const updateFunc = () => authFetch('api/missiles', {
            method: 'post',
            body: JSON.stringify(form.values),
        }).then(r => r.json()).then(r => setResults((previous) => previous.concat(r)));
        props.updateData(['missiles', 'kingdom'], [updateFunc]);
    };

    const columns = [
        { header: "Missile", align: "left", cell: ({ label }) => label },
        {
            header: "Built", span: (missile) => (locked(missile) ? 2 : 1),
            cell: (missile) => locked(missile) ? `Research "${missile.projectName}" Project to Unlock` : (info.current[missile.key] || 0).toLocaleString(),
        },
        { header: "Building", cell: ({ key }) => (info.building[key] || 0).toLocaleString() },
        { header: "Capacity", cell: () => (info.capacity || 0).toLocaleString() },
        { header: "Build Time", cell: () => toHHMMSS(info.build_time || 0) },
        { header: "Cost", cell: ({ key }) => Math.floor((info.desc[key].cost || 0) * info.cost_modifier).toLocaleString() },
        { header: "Fuel Cost", cell: ({ key }) => Math.floor((info.desc[key].fuel_cost || 0) * info.cost_modifier).toLocaleString() },
        {
            header: "To Build",
            cell: (missile) => <AmountInput
                name={missile.key} label={missile.label} id={missile.key.replace("_", "-") + "-input"}
                value={form.values[missile.key]} onChange={form.onChange} error={fieldErrors[missile.key]}
                max={maxFor(missile)} soloMax={soloFor(missile)} disabled={locked(missile)}
            />,
        },
    ];

    return (
        <>
            <Header data={props.data} />
            <div className="missiles">
                <ResultToasts title="Missiles Results" results={results} setResults={setResults} />
                <GameTable
                    className="missiles-table" columns={columns} rows={MISSILES} rowKey={({ key }) => key}
                    rowClassName={(missile) => (locked(missile) ? "disabled-table-row" : undefined)}
                />
                <SubmitButton loading={props.loading.missiles} blocked={blocked} className="missiles-button" onClick={onSubmitClick}>
                    Build
                </SubmitButton>
                {cost !== 0
                    ? <div>
                        <h3>Missiles Cost: {cost.toLocaleString()}</h3>
                        <h3>Missiles Fuel Cost: {fuelCost.toLocaleString()}</h3>
                    </div>
                    : null}
                <HelpButton scrollTarget={"buildmissiles"}/>
            </div>
        </>
    );
}

export default Missiles;
