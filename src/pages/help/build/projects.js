import { displayPercent } from "../../../format";
import { inOrder } from "../../../order";
import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Projects(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "projects") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const prettyNames = props.state.pretty_names || {};
    const projectsDesc = props.state.projects || {};
    const categories = props.state.project_categories || {};
    const projectsRows = inOrder(Object.keys(projectsDesc), props.state.order?.projects).map((projectsKey, iter) => {
        const project = projectsDesc[projectsKey];
        const requires = [
            ...(project.requires || []).map((required) => projectsDesc[required]?.name || required),
            ...(project.race ? [`${project.race} only`] : []),
        ];
        return <tr key={"projects_" + iter}>
            <td style={{textAlign: "left"}}>{project.name}</td>
            <td style={{textAlign: "left"}}>{categories[project.category] || project.category}</td>
            <td style={{textAlign: "left"}}>
                {project.max_bonus !== undefined
                    ? `Continuous, up to ${displayPercent(project.max_bonus)}`
                    : `One-time, ${Math.floor(project.constant || 0).toLocaleString()} points`
                        + (project.bonus !== undefined ? `, ${displayPercent(project.bonus)} once completed` : "")}
            </td>
            <td style={{textAlign: "left"}}>{requires.join(", ")}</td>
            <td style={{textAlign: "left"}}>{project.desc}</td>
        </tr>
    })
    return (
        <div id="projects" ref={yourElementRef} className="help-section">
            <h2>Build - Projects</h2>
            <p>
                The Train page allows you to train engineers. You can train 
                up to {displayPercent(props.state.game_config?.BASE_MAX_ENGINEERS_POP_CAP)} of your
                current population at one time as long as you have workshop capacity.
            </p>
            <p>
                Base engineers training cost is {props.state.game_config?.BASE_ENGINEER_COST}. 
                The base average training time is {props.state.game_config?.BASE_EPOCH_SECONDS * (props.state.game_config?.BASE_ENGINEER_TIME_MIN_MULTIPLIER + props.state.game_config?.BASE_ENGINEER_TIME_MAX_MUTLIPLIER) / 2 / 3600} hours.
            </p>
            <p>
                Each engineer produces {props.state.game_config?.BASE_ENGINEER_PROJECT_POINTS_PER_EPOCH} project points
                per {props.state.game_config?.BASE_EPOCH_SECONDS} seconds.
            </p>
            <p>
                The Assign page allow you to assign available engineers to your projects. The Assign column overwrites currently 
                assigned engineers across all projects, while the Add column is used to add engineers to projects.
            </p>
            <p>
                The "Continuous Projects" are projects whose maximum points increases as your stars increase, generally at a rate of 
                stars ^ 1.5. These projects will become exponentially more difficult to keep maxed as the game progresses, so you will 
                likely have to choose which projects you would like to invest in.
            </p>
            <p>
                The "One-Time Projects" are projects which provide some benefit after they are completed. Once you have finished these projects, 
                you will no longer be able to assign engineers to these projects.
            </p>
            <p>
                Some projects need others first: engineers can only work on a project once every project in its
                "Requires" column is completed. Racial projects can only be researched by kingdoms of that race, and
                you only see your own race's.
            </p>
            <p>
                The Allocate page allows you to set the target allocation of engineers across all projects. When enabled, engineers will be 
                automatically assigned to projects at the percentages you have chosen during each game update.
            </p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Project</th>
                        <th>Category</th>
                        <th>Kind</th>
                        <th>Requires</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {projectsRows}
                </tbody>
            </Table>
        </div>
    )
}

export default Projects;