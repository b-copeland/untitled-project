import React from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./scores.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { GameTable } from "../../components/gametable";

const kingdomLabel = (data, kdId) => (
    kdId !== "" ? `${data.kingdoms[parseInt(kdId)]} (${data.galaxies_inverted[kdId]})` : "Unknown"
);

const decimals = (value) => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * One leaderboard. ``rows`` are [id, value] pairs, best first. Your own kingdom is highlighted and your rank stated
 * above the table, because on a long list the first question is always "where am I?". Kingdoms in your galaxy are
 * tinted too, since the galaxy is the team.
 */
function Leaderboard({ rows, valueHeader, nameHeader = "Kingdom", label, formatValue = (value) => value.toLocaleString(), mine, mates = [] }) {
    const yourIndex = rows.findIndex(([id]) => mine !== undefined && String(id) === String(mine));
    const above = yourIndex > 0 ? rows[yourIndex - 1] : null;
    const gap = above ? Number(above[1]) - Number(rows[yourIndex][1]) : 0;
    const rank = yourIndex >= 0
        ? `You are ranked ${yourIndex + 1} of ${rows.length}.` + (above ? ` ${formatValue(gap)} more to pass ${label(above[0])}.` : " You are in the lead.")
        : null;
    const columns = [
        { header: "Rank", align: "left", cell: (_, index) => index + 1 },
        { header: nameHeader, align: "left", cell: ([id]) => label(id) },
        { header: valueHeader, cell: ([, value]) => formatValue(value) },
    ];
    const rowClassName = ([id]) => (
        String(id) === String(mine) ? "scores-you" : mates.includes(String(id)) ? "scores-mate" : undefined
    );
    return (
        <div className="kingdom">
            {rank ? <p className="scores-rank">{rank}</p> : null}
            <GameTable
                className="scores-table" columns={columns} rows={rows} rowClassName={rowClassName}
                rowKey={([id]) => id} size="sm"
            />
        </div>
    );
}

function Scores(props) {
    const { data } = props;
    const mine = data.kingdomid?.kd_id;
    const galaxy = data.galaxies_inverted?.[mine];
    const mates = Object.keys(data.galaxies_inverted || {}).filter((id) => data.galaxies_inverted[id] === galaxy && id !== String(mine));
    const shared = { mine, mates, label: (id) => kingdomLabel(data, id) };

    return (
        <>
            <Header data={data} />
            <Tabs id="controlled-tab-example" defaultActiveKey="points" justify fill variant="tabs">
                <Tab eventKey="points" title="Points">
                    <Leaderboard rows={data.scores?.points || []} valueHeader="Points" formatValue={decimals} {...shared} />
                </Tab>
                <Tab eventKey="networth" title="Networth">
                    <Leaderboard rows={data.scores?.networth || []} valueHeader="Networth" {...shared} />
                </Tab>
                <Tab eventKey="stars" title="Stars">
                    <Leaderboard rows={data.scores?.stars || []} valueHeader="Stars" {...shared} />
                </Tab>
                <Tab eventKey="galaxy" title="Galaxy Networth">
                    <Leaderboard
                        rows={data.scores?.galaxy_networth || []} valueHeader="Networth" nameHeader="Galaxy"
                        label={(id) => id} mine={galaxy} mates={[]}
                    />
                </Tab>
            </Tabs>
            <HelpButton scrollTarget={"scores"}/>
        </>
    );
}

export { Leaderboard };
export default Scores;
