import React, { useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';
import Button from "react-bootstrap/Button";
import { Link } from "react-router-dom";
import "./scores.css";
import HelpButton from "../../components/helpbutton";
import { GameTable } from "../../components/gametable";
import { Panel } from "../../components/planner";
import { KingdomLink, kingdomLabel } from "../../components/kingdomlink";
import { useFromHere } from "../../components/pagehead";

const decimals = (value) => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** How many rows a leaderboard shows before "Show all". */
const TOP = 10;

/**
 * One leaderboard. ``rows`` are [id, value] pairs, best first. Your own kingdom is highlighted and your rank stated
 * at the top, because on a long list the first question is always "where am I?". Kingdoms in your galaxy are tinted
 * too, since the galaxy is the team. It shows the top ten, and your row under them when you are further down, until
 * "Show all".
 */
function Leaderboard({ title, rows, valueHeader, nameHeader = "Kingdom", label, formatValue = (value) => value.toLocaleString(), mine, mates = [] }) {
    const [all, setAll] = useState(false);
    const yourIndex = rows.findIndex(([id]) => mine !== undefined && String(id) === String(mine));
    const rank = yourIndex >= 0 ? `You are ranked ${yourIndex + 1} of ${rows.length}.` : null;
    const ranked = rows.map((row, index) => [...row, index + 1]);
    const shown = all ? ranked : ranked.filter(([, , place]) => place <= TOP || place === yourIndex + 1);
    const columns = [
        { header: "Rank", align: "left", cell: ([, , place]) => place },
        { header: nameHeader, align: "left", cell: ([id]) => label(id) },
        { header: valueHeader, cell: ([, value]) => formatValue(value) },
    ];
    const rowClassName = ([id, , place]) => [
        String(id) === String(mine) ? "scores-you" : mates.includes(String(id)) ? "scores-mate" : "",
        !all && place > TOP ? "scores-gap" : "",
    ].filter(Boolean).join(" ") || undefined;
    return (
        <Panel title={title} className="scores-board">
            {rank ? <p className="scores-rank">{rank}</p> : null}
            <GameTable className="game-table scores-table" columns={columns} rows={shown} rowClassName={rowClassName}
                rowKey={([id]) => id} size="sm" />
            {rows.length > TOP
                ? <Button variant="link" size="sm" className="scores-more" onClick={() => setAll(!all)}>
                    {all ? `Show the top ${TOP}` : `Show all ${rows.length}`}
                </Button>
                : null}
        </Panel>
    );
}

/** A galaxy's id, linking to it on the Galaxy page. */
function GalaxyLink({ id }) {
    const state = useFromHere();
    return <Link className="kingdom-link" to={`/galaxy?galaxy=${encodeURIComponent(id)}`} state={state}>{id}</Link>;
}

function Scores(props) {
    const { data } = props;
    const mine = data.kingdomid?.kd_id;
    const galaxy = data.galaxies_inverted?.[mine];
    const mates = Object.keys(data.galaxies_inverted || {}).filter((id) => data.galaxies_inverted[id] === galaxy && id !== String(mine));
    // Kingdoms the scores do not name (hidden by the server) stay "Unknown", with no link.
    const label = (id) => (id !== "" ? <KingdomLink kdId={id} data={data}>{kingdomLabel(data, id)}</KingdomLink> : "Unknown");
    const shared = { mine, mates, label };

    return (
        <div className="scores panel-grid">
            <Leaderboard title="Points" rows={data.scores?.points || []} valueHeader="Points" formatValue={decimals} {...shared} />
            <Leaderboard title="Networth" rows={data.scores?.networth || []} valueHeader="Networth" {...shared} />
            <Leaderboard title="Stars" rows={data.scores?.stars || []} valueHeader="Stars" {...shared} />
            <Leaderboard title="Galaxy networth" rows={data.scores?.galaxy_networth || []} valueHeader="Networth" nameHeader="Galaxy"
                label={(id) => <GalaxyLink id={id} />} mine={galaxy} mates={[]} />
            <HelpButton scrollTarget={"scores"}/>
        </div>
    );
}

export { Leaderboard };
export default Scores;
