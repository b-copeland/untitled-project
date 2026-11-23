import React from "react";
import { HelpTable, Topic, config, duration, num } from "../util";

function Home(props) {
    const values = config(props.state).NETWORTH_VALUES || {};
    const names = props.state.pretty_names || {};
    const horizons = config(props.state).QUEUE_FORECAST_EPOCHS || [];
    return (
        <Topic id="home" title="Status" lead="Your kingdom at a glance.">
            <ul>
                <li><b>Overview</b>: your economy, military, growth and threats on four cards. Each card's title links to the page where you act on it.</li>
                <li><b>Since you were last here</b>: on the Overview, what changed while you were away: stars, networth, population, drones, engineers, each military unit and structure, and the attacks, spy operations and missiles against you. It counts from your last visit on this device when that was an hour or more ago, and covers the last hour otherwise. Your kingdom is recorded every half hour, so it counts from the record just before your visit, and units and structures go back a week at most.</li>
                <li><b>Kingdom</b>: your resources, income and population. Income adds up continuously, not in steps.</li>
                <li><b>Military</b>: your units at home and with each general, and when each general returns.</li>
                <li><b>Structures</b>: what is built and what is still being built.</li>
            </ul>
            <p>
                <b>Max offense</b> and <b>max defense</b> on the Military tab assume your best case: military
                efficiency and military shields at their maximum, all four generals sent, and fuel in stock.
            </p>
            {horizons.length > 0 && (
                <p>
                    The Military and Structures tabs also show what you will have as training and building finish,
                    from {duration(horizons[0], config(props.state))} to {duration(horizons[horizons.length - 1], config(props.state))} ahead.
                </p>
            )}
            <h4>Networth</h4>
            <p>Networth adds up the values below. It sets your rank on the Scores page, which earns points.</p>
            <HelpTable columns={[["Item"], ["Networth each", "right"]]}
                rows={Object.keys(values).map((key) => [names[key] || key, num(values[key])])} />
        </Topic>
    );
}

export default Home;
