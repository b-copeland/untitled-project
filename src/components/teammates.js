import React from "react";
import Alert from "react-bootstrap/Alert";

/*
 * Galaxymates and empire-mates on the pages that harm a kingdom (Attack, Spy, Launch Missiles): the target picker tags
 * and shades them, and choosing one puts a warning on the page and a confirmation before sending. The server still
 * lets a player act against their own team; this is only so nobody does it by accident.
 */

const myKd = (data) => String(data.kingdomid?.kd_id ?? "");

/** "galaxy" if ``kdId`` is in the player's galaxy, "empire" if in another galaxy of the player's empire, else null. */
export function teamOf(data, kdId) {
    const me = myKd(data);
    const id = String(kdId ?? "");
    if (!me || !id || id === me) return null;
    const galaxies = data.galaxies_inverted || {};
    if (galaxies[me] !== undefined && galaxies[id] === galaxies[me]) return "galaxy";
    const empires = data.empires_inverted?.empires_inverted || {};
    if (empires[me] !== undefined && empires[me] !== null && empires[id] === empires[me]) return "empire";
    return null;
}

export const TEAM_TAGS = { galaxy: "Your galaxy", empire: "Your empire" };

/** The picker's options: every kingdom but the player's own, as "Name (1:3)", each with its ``team``. */
export function targetOptions(data) {
    const me = myKd(data);
    return Object.keys(data.kingdoms || {})
        .filter((kdId) => kdId !== me)
        .map((kdId) => ({
            value: kdId,
            label: `${data.kingdoms[kdId]} (${(data.galaxies_inverted || {})[kdId]})`,
            team: teamOf(data, kdId),
        }));
}

/** A small tag for a teammate, for a picker option or beside a name. */
export function TeamTag({ team }) {
    if (!team) return null;
    return <span className="status-tag tag-team" title="On your own team: anything you do to them hurts your side">{TEAM_TAGS[team]}</span>;
}

/** How a picker option shows: the label, then the tag if it is a teammate. */
export const teamOptionLabel = (option) => <span>{option.label}<TeamTag team={option.team} /></span>;

const ON_TEAM = {
    galaxy: "is in your galaxy",
    empire: "is in your empire",
};

/** The warning on the page once a teammate is chosen. ``doing`` is what the page does to them ("Attacking them"). */
export function TeammateWarning({ data, target, doing }) {
    const team = teamOf(data, target);
    if (!team) return null;
    return (
        <Alert variant="warning" className="teammate-warning mt-2 mb-0">
            <strong>{data.kingdoms?.[target]} {ON_TEAM[team]}.</strong> {doing} hurts your own team.
        </Alert>
    );
}
