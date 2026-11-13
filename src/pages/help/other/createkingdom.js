import { raceDescriptions } from "../../../races";
import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function CreateKingdom(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "createkingdom") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);

    const lines = (list) => list.map((line, index) => <React.Fragment key={line}>{index > 0 ? <br/> : null}<span>{line}</span></React.Fragment>);
    const racesDesc = raceDescriptions(props.state.game_config);
    const racesRows = Object.keys(racesDesc).map((racesKey, iter) => {
        return <tr key={"races_" + iter}>
            <td style={{textAlign: "left"}}>{racesKey}</td>
            <td style={{textAlign: "left"}}>{lines(racesDesc[racesKey].pros)}</td>
            <td style={{textAlign: "left"}}>{lines(racesDesc[racesKey].cons)}</td>
        </tr>
    })
    return (
        <div id="createkingdom" ref={yourElementRef} className="help-section">
            <h2>Create Kingdom</h2>
            <p>
                Making your kingdom takes three steps: choose a name, choose how you want to play, and check the result. Nothing is
                made until the last button. You will be placed in the galaxy with the fewest kingdoms.
            </p>
            <p>
                The quick starts (Explorer, Attacker, Intel and Thief) are each a race and a starting kingdom, with a ready-made plan for
                the auto builder. The plan is always saved with your kingdom; you are asked whether to switch the auto builder on. Left
                off, nothing is spent or sent until you do it yourself, and you can switch it on later from the Status page (auto
                spending) and the Primitives page (auto attack and robbing).
            </p>
            <p>
                Custom lets you spend the starting unit points and stars yourself. You must use all of both. The numbers under
                the choices update as you change them.
            </p>
            <Table striped bordered hover size="sm" className="races-table">
                <thead>
                    <tr>
                        <th>Race</th>
                        <th>Pros</th>
                        <th>Cons</th>
                    </tr>
                </thead>
                <tbody>
                    {racesRows}
                </tbody>
            </Table>
        </div>
    )
}

export default CreateKingdom;
