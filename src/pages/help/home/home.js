import React from "react";
import { HelpTable, Topic, config, num } from "../util";

function Home(props) {
    const values = config(props.state).NETWORTH_VALUES || {};
    const names = props.state.pretty_names || {};
    return (
        <Topic id="home" title="Status" lead="Your kingdom at a glance.">
            <ul>
                <li><b>Overview</b>: your economy, military, growth and threats on four cards. Each card's title links to the page where you act on it.</li>
                <li><b>Kingdom</b>: your resources, income and population. Income adds up continuously, not in steps.</li>
                <li><b>Military</b>: your units at home and with each general, and when each general returns.</li>
                <li><b>Structures</b>: what is built and what is still being built.</li>
            </ul>
            <p>
                <b>Max offense</b> and <b>max defense</b> on the Military tab assume your best case: military
                efficiency and military shields at their maximum, all four generals sent, and fuel in stock.
            </p>
            <h4>Networth</h4>
            <p>Networth adds up the values below. It sets your rank on the Scores page, which earns points.</p>
            <HelpTable columns={[["Item"], ["Networth each", "right"]]}
                rows={Object.keys(values).map((key) => [names[key] || key, num(values[key])])} />
        </Topic>
    );
}

export default Home;
