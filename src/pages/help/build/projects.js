import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Projects(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    const prettyNames = props.state.pretty_names || {};
    const projectsDesc = props.state.projects || {};
    const projectsRows = Object.keys(projectsDesc).map((projectsKey, iter) => {
        return <tr key={"projects_" + iter}>
            <td style={{textAlign: "left"}}>{projectsDesc[projectsKey].name}</td>
            <td style={{textAlign: "left"}}>{projectsDesc[projectsKey].desc}</td>
        </tr>
    })
    return (
        <div id="projects" className="help-section">
            <h2>Build - Projects</h2>
            <p>
                The Train page allows you to train engineers. You can train 
                up to {displayPercent(props.state.game_config?.BASE_MAX_ENGINEERS_POP_CAP)} of your
                current population at one time as long as you have workshop capacity.
            </p>
            <p>
                Base engineers training cost is {props.state.game_config?.BASE_ENGINEER_COST}. 
                The base training time is {props.state.game_config?.BASE_EPOCH_SECONDS * props.state.game_config?.BASE_ENGINEER_TIME_MULTIPLIER / 3600} hours.
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
                The Allocate page allows you to set the target allocation of engineers across all projects. When enabled, engineers will be 
                automatically assigned to projects at the percentages you have chosen during each game update.
            </p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Project</th>
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