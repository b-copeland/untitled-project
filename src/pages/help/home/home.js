import React from "react";
import { HelpTable, Topic, config, duration, num } from "../util";

function Home(props) {
    const values = config(props.state).NETWORTH_VALUES || {};
    const names = props.state.pretty_names || {};
    const horizons = config(props.state).QUEUE_FORECAST_EPOCHS || [];
    return (
        <Topic id="home" title="Status" lead="Your kingdom at a glance.">
            <ul>
                <li><b>Overview</b>: first your advisors, then your economy, military, growth and threats on four cards. Each card's title links to the page where you act on it.</li>
                <li><b>Kingdom</b>: your resources, income and population. Income adds up continuously, not in steps.</li>
                <li><b>Military</b>: your units at home and with each general, and when each general returns.</li>
                <li><b>Structures</b>: what is built and what is still being built.</li>
            </ul>
            <p>
                <b>Max offense</b> and <b>max defense</b> on the Military tab assume your best case: military
                efficiency and military shields at their maximum, all four generals sent, and fuel in stock. The
                Overview's Military card shows your defense and offense at home as they are now instead: your real
                military efficiency, shields and fuel, and the generals at home.
            </p>
            {horizons.length > 0 && (
                <p>
                    The Military and Structures tabs also show what you will have as training and building finish,
                    from {duration(horizons[0], config(props.state))} to {duration(horizons[horizons.length - 1], config(props.state))} ahead.
                </p>
            )}
            <h4>Advisors</h4>
            <p>
                Your advisors point out what in your kingdom may need fixing, most serious first, with links to where
                you fix it. Warnings in red are about harm happening now, such as fuel running out or a defense so low
                that attacking you pays better than attacking primitives; they go away once the problem is fixed.
                The rest point out money, land, engineers, generals or spy attempts sitting idle, and things your
                galaxy, cluster, empire or the universe is waiting on, such as a vote. Advice only a galaxy leader can
                act on goes only to the leader. And they tell you when your kingdom is far behind almost every other
                kingdom in the universe on something that matters, such as income or defense per star, without saying
                how anyone else stands. Other advice can be hidden for good with <b>Hide</b>, and shown again from <b>Show hidden advice</b>.
                You can turn the advisors off in Settings.
            </p>
            <h4>Networth</h4>
            <p>Networth adds up the values below. It sets your rank on the Scores page, which earns points.</p>
            <HelpTable columns={[["Item"], ["Networth each", "right"]]}
                rows={Object.keys(values).map((key) => [names[key] || key, num(values[key])])} />
        </Topic>
    );
}

export default Home;
