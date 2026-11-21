import React from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { GiCrossedSwords } from "react-icons/gi";
import { BsBinoculars, BsRocketTakeoff } from "react-icons/bs";
import { KingdomTabs } from "./conquer/intel.js";
import { targetPath } from "../components/kingdomlink";
import { useFromHere } from "../components/pagehead";
import "./kingdom.css";

/*
 * One kingdom's page (/kingdom/12, or /kingdom/12?tab=intel): what you know about it and its intel market, with links
 * to attack, spy on or launch missiles at it. Every kingdom name in the game links here (components/kingdomlink.js).
 */

const ACTIONS = [
    { page: "/attack", label: "Attack", icon: GiCrossedSwords },
    { page: "/spy", label: "Spy", icon: BsBinoculars },
    { page: "/launchmissiles", label: "Launch missiles", icon: BsRocketTakeoff },
];

function KingdomPage(props) {
    const { kdid } = useParams();
    const [query] = useSearchParams();
    const fromHere = useFromHere();
    const mine = String(props.data.kingdomid?.kd_id ?? "") === String(kdid);
    return (
        <div className="kingdom-page">
            {mine ? null : (
                <div className="kingdom-page-actions">
                    {ACTIONS.map(({ page, label, icon: Icon }) => (
                        <Link key={page} className="btn btn-sm btn-outline-primary" to={targetPath(page, kdid)} state={fromHere}>
                            <Icon aria-hidden="true" /> {label}
                        </Link>
                    ))}
                </div>
            )}
            <KingdomTabs target={kdid} tab={query.get("tab") || "kingdom"}
                data={props.data} loading={props.loading} updateData={props.updateData} />
        </div>
    );
}

export default KingdomPage;
