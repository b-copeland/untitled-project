import React from "react";
import { displayPercent } from "../../../format";
import { inOrder } from "../../../order";
import { HelpTable, Topic, averageDuration, config, num, pct, perHour } from "../util";

function Projects(props) {
    const cfg = config(props.state);
    const projects = props.state.projects || {};
    const categories = props.state.project_categories || {};
    const rows = inOrder(Object.keys(projects), props.state.order?.projects).map((key) => {
        const project = projects[key];
        const requires = [
            ...(project.requires || []).map((required) => projects[required]?.name || required),
            ...(project.race ? [`${project.race} only`] : []),
        ];
        const kind = project.max_bonus !== undefined
            ? `Continuous, up to ${displayPercent(project.max_bonus)}`
            : `One-time, ${num(Math.floor(project.constant || 0))} points`
                + (project.bonus !== undefined ? `, +${displayPercent(project.bonus)}` : "");
        return [project.name, categories[project.category] || project.category, kind, requires.join(", "), project.desc];
    });
    return (
        <Topic id="projects" title="Projects" lead="Engineers earn points that improve almost every part of your kingdom.">
            <ul>
                <li><b>Train</b>: engineers cost {num(cfg.BASE_ENGINEER_COST)} and take {averageDuration(cfg.BASE_ENGINEER_TIME_MIN_MULTIPLIER, cfg.BASE_ENGINEER_TIME_MAX_MUTLIPLIER, cfg)} on average. You can train up to {pct(cfg.BASE_MAX_ENGINEERS_POP_CAP)} of your population at once, and each engineer needs room in a workshop.</li>
                <li><b>Assign</b>: set how many engineers work on each project with its slider, then press Update. Each engineer earns {num(perHour(cfg.BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH, cfg))} points per hour.</li>
                <li><b>Allocate</b>: give each project a share of your engineers and turn on auto assign. Every game update moves engineers to match the shares.</li>
            </ul>
            <h4>Two kinds of project</h4>
            <ul>
                <li><b>Continuous</b>: the bonus grows with the project's points, up to its maximum. The points needed for the maximum grow with your stars (about stars<sup>1.5</sup>), so you can not keep them all at the top. Choose the ones that matter most to you.</li>
                <li><b>One-time</b>: finish it once to unlock a unit or an operation, or to get a fixed bonus. A finished project takes no more engineers.</li>
            </ul>
            <p>
                A project can need others first (the Requires column). Racial projects are for that race only, and you
                only see your own race's.
            </p>
            <HelpTable columns={[["Project"], ["Category"], ["Kind"], ["Requires"], ["What it does"]]} rows={rows} />
        </Topic>
    );
}

export default Projects;
