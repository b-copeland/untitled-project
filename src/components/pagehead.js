import React, { createContext, useContext } from "react";
import { Link, useLocation } from "react-router-dom";

/*
 * The frame of every game page (App.js): the page's title under its section's name, and, when another page sent the
 * player here, a link back to it. Links that leave a page say where they came from with ``fromHere()``, so the next
 * page can offer the way back.
 */

/** The page on screen: its path (with the query) and its title. Set by App.js around each game page. */
export const PageContext = createContext({ path: "/status", label: "Status" });

/** The ``state`` a link passes so the page it opens can link back here: ``<Link to=... state={useFromHere()}>``. */
export function useFromHere() {
    const page = useContext(PageContext);
    return { from: { path: page.path, label: page.label } };
}

/** The section name (or the way back), then the title. */
export function PageHead({ section, title }) {
    const from = useLocation().state?.from;
    return (
        <div className="page-head">
            {from
                ? <nav className="page-crumbs" aria-label="Breadcrumb"><Link to={from.path}>&lsaquo; {from.label}</Link></nav>
                : <div className="page-crumbs">{section}</div>}
            <h1 className="page-title">{title}</h1>
        </div>
    );
}
