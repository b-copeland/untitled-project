import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Table from 'react-bootstrap/Table';

function Home(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "home") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    const nwRows = Object.keys(props.state.game_config?.NETWORTH_VALUES || {}).map((keyItem, iter) => {
        return <tr key={"networthvalues_" + iter}>
            <td style={{textAlign: "left"}}>{props.state.pretty_names[keyItem] || keyItem}</td>
            <td style={{textAlign: "right"}}>{props.state.game_config?.NETWORTH_VALUES[keyItem]}</td>
        </tr>
    })
    return (
        <div id="home" ref={yourElementRef} className="help-section">
            <h2>Home</h2>
            <h4>Home - Kingdom</h4>
            <p>The kingdom page displays information about your kingdom's status, such as networth, stars, and units.</p>
            <p>
                Additionally, you can view your kingdom's current income. 
                Income is updated continuously as the game progresses. Income is continuously accumulated as the game progresses, 
                based on the number of seconds elapsed since the last update. Updates occur every 15 to 60 seconds, based on the
                current game config.
            </p>
            <p>Networth is calculated by summing the values below</p>
            <Table striped bordered hover>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Networth Value</th>
                    </tr>
                </thead>
                <tbody>
                    {nwRows}
                </tbody>
            </Table>
            <h4>Home - Military</h4>
            <p>
                The military page displays the current status of your generals and the production status of your military.
            </p>
            <p>
                The max offense and max defense statistics are calculated assuming that your kingdom has the max possible bonuses, 
                that is: your military efficiency is maxed, your military shields are maxed, you are sending 4 generals, and you are not fuelless.
            </p>
            <h4>Home - Structures</h4>
            <p>
                The structures page displays the current and future status of your structures.
            </p>
        </div>
    )
}

export default Home;