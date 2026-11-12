import React, { useEffect, useState } from "react";
import { authFetch } from "../../auth";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import "./news.css"
import Header from "../../components/header";
import 'bootstrap/dist/css/bootstrap.css';
import HelpButton from "../../components/helpbutton";

/** "5m ago", "3h ago", "2d ago". The exact time is in the tooltip. */
export function timeAgo(date, now = Date.now()) {
    const seconds = Math.max(Math.floor((now - Date.parse(date)) / 1000), 0);
    if (seconds < 60) return "just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 48 * 3600) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

const getNotifsSuffix = (notifs, categories) => {
    const count = categories.reduce((total, category) => total + (parseInt(notifs?.[category]) || 0), 0);
    return count > 0 ? ` (${count})` : "";
};

const PAGE = 20;

/**
 * News as a feed, newest first: how long ago, who it concerns, and the item. ``items`` are {time, from, to, news};
 * ``name(id)`` turns a kingdom id into a label. The search box filters on the text and the names.
 */
export function NewsFeed({ items, name, empty = "Nothing yet." }) {
    const [search, setSearch] = useState("");
    const [shown, setShown] = useState(PAGE);
    const newestFirst = [...items].sort((a, b) => Date.parse(b.time) - Date.parse(a.time));
    const labelled = newestFirst.map((item) => ({
        ...item,
        fromLabel: item.from ? name(item.from) : "",
        toLabel: item.to ? name(item.to) : "",
    }));
    const needle = search.trim().toLowerCase();
    const matching = needle
        ? labelled.filter((item) => [item.news, item.fromLabel, item.toLabel].some((text) => String(text).toLowerCase().includes(needle)))
        : labelled;
    return (
        <div className="news-feed">
            <Form.Control
                className="news-search" size="sm" type="search" placeholder="Search the news" aria-label="Search the news"
                value={search} onChange={(e) => { setSearch(e.target.value); setShown(PAGE); }}
            />
            {matching.length === 0 ? <p className="news-empty">{items.length === 0 ? empty : "Nothing matches."}</p> : null}
            <ul className="news-list">
                {matching.slice(0, shown).map((item, index) => (
                    <li key={item.time + "|" + index} className="news-item">
                        <div className="news-meta">
                            <time dateTime={item.time} title={new Date(item.time).toLocaleString()}>{timeAgo(item.time)}</time>
                            {item.fromLabel ? <span className="news-who">from {item.fromLabel}</span> : null}
                            {item.toLabel ? <span className="news-who">to {item.toLabel}</span> : null}
                        </div>
                        <div className="news-text">{item.news}</div>
                    </li>
                ))}
            </ul>
            {matching.length > shown
                ? <Button variant="outline-secondary" size="sm" onClick={() => setShown(shown + PAGE)}>
                    Show more ({matching.length - shown} older)
                </Button>
                : null}
        </div>
    );
}

function NewsContent(props) {
    const clearNotifs = (categories) => {
        const updateFunc = () => {
            authFetch("api/clearnotifs", {
                method: "POST",
                body: JSON.stringify({"categories": categories})
            });
        }
        props.updateData(['notifs'], [updateFunc])
    }
    useEffect(() => {
        clearNotifs(["news_kingdom"])
    }, [])

    if (Object.keys(props.data.galaxies_inverted).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdoms).length === 0) {
        return null;
    }
    const handleNotifsSelect = (eventKey) => {
        if (eventKey === "kingdom" && props.data.notifs.news_kingdom > 0) {
            clearNotifs(["news_kingdom"])
        } else if (eventKey === "galaxy" && props.data.notifs.news_galaxy > 0) {
            clearNotifs(["news_galaxy"])
        }
    }
    const name = (kdId) => `${props.data.kingdoms[parseInt(kdId)]} (${props.data.galaxies_inverted[kdId]})`;
    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
        onSelect={handleNotifsSelect}
      >
        <Tab eventKey="kingdom" title={`Kingdom${getNotifsSuffix(props.data.notifs, ["news_kingdom"])}`}>
          <NewsFeed items={props.data.news || []} name={name} />
        </Tab>
        <Tab eventKey="galaxy" title={`Galaxy${getNotifsSuffix(props.data.notifs, ["news_galaxy"])}`}>
          <NewsFeed items={props.data.galaxynews || []} name={name} />
        </Tab>
        <Tab eventKey="empire" title="Empire">
          <NewsFeed items={props.data.empirenews || []} name={name} />
        </Tab>
        <Tab eventKey="universe" title="Universe">
          <NewsFeed items={props.data.universenews || []} name={name} />
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"news"}/>
    </>
    );
}

export default NewsContent;
