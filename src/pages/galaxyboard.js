import React, { useEffect, useState } from "react";
import Form from "react-bootstrap/Form";
import { BsPinAngle, BsPinAngleFill } from "react-icons/bs";
import { FiTrash2 } from "react-icons/fi";
import { authFetch } from "../auth";
import { IconButton } from "../components/iconbutton";
import { KingdomLink } from "../components/kingdomlink";
import { Panel } from "../components/planner";
import { ResultToasts, safeJson } from "../components/results";
import { SubmitButton } from "../components/forms";
import { checkPost } from "../validation";
import "./galaxyboard.css";

const LINK = /(https?:\/\/[^\s]+)/;

/** The post's text, with web addresses as links that open in a new tab. Everything else is plain text. */
export function PostText({ text }) {
    return (
        <p className="board-text">
            {String(text).split(LINK).map((part, index) => (index % 2 === 1
                ? <a key={index} href={part} target="_blank" rel="noopener noreferrer nofollow">{part}</a>
                : <React.Fragment key={index}>{part}</React.Fragment>))}
        </p>
    );
}

function Post({ post, kingdoms, mine, canModerate, pinned, onDelete, onPin }) {
    return (
        <li className={"board-post" + (pinned ? " board-post-pinned" : "")}>
            <div className="board-post-head">
                <span>
                    <KingdomLink kdId={post.from}>{kingdoms[post.from] || `Kingdom ${post.from}`}</KingdomLink>
                    <time dateTime={post.time}>{new Date(post.time).toLocaleString([], { dateStyle: "short", timeStyle: "short" })}</time>
                </span>
                <span className="board-post-actions">
                    {canModerate && onPin
                        ? <IconButton icon={pinned ? BsPinAngleFill : BsPinAngle} label={pinned ? "Unpin" : "Pin to the top"} onClick={onPin} active={pinned} />
                        : null}
                    {mine || canModerate ? <IconButton icon={FiTrash2} label="Delete" onClick={onDelete} /> : null}
                </span>
            </div>
            <PostText text={post.text} />
        </li>
    );
}

/**
 * The galaxy board: posts every kingdom in the galaxy can read, newest first, for coordinating (a Discord invite, a
 * plan for the night). The galaxy leader can pin one post to the top and delete any; others delete their own.
 */
function GalaxyBoard(props) {
    const [draft, setDraft] = useState("");
    const [results, setResults] = useState([]);
    const board = props.data.galaxyboard || {};
    const kingdoms = props.data.kingdoms || {};
    const me = props.data.kingdomid?.kd_id;
    const max = props.data.state?.game_config?.GALAXY_BOARD_MAX_LENGTH;
    const posts = board.posts || [];
    const pinned = board.pinned || null;

    useEffect(() => {
        const updateFunc = () => authFetch("api/clearnotifs", { method: "POST", body: JSON.stringify({ categories: ["galaxy_board"] }) });
        props.updateData(["notifs"], [updateFunc]);
    }, []);

    const send = (path, body, after) => {
        const updateFunc = async () => authFetch(path, { method: "POST", body: JSON.stringify(body || {}) })
            .then(safeJson).then((r) => { setResults((previous) => previous.concat(r)); if (r.status === "success" && after) after(); });
        props.updateData(["galaxyboard"], [updateFunc]);
    };
    const blocked = checkPost(draft, max);
    const post = (event) => {
        event.preventDefault();
        if (!blocked) send("api/galaxyboard", { text: draft }, () => setDraft(""));
    };
    const remove = (postId) => send(`api/galaxyboard/${postId}/delete`);
    const pin = (postId) => send(`api/galaxyboard/${postId}/pin`);
    const unpin = () => send("api/galaxyboard/unpin");
    const length = draft.trim().length;

    return (
        <div className="galaxy-board">
            <ResultToasts title="Galaxy Board" results={results} setResults={setResults} />
            {pinned
                ? <Panel title="Pinned">
                    <ul className="board-posts">
                        <Post post={pinned} kingdoms={kingdoms} mine={pinned.from === me} canModerate={board.can_moderate} pinned
                            onPin={unpin} onDelete={() => remove(pinned.id)} />
                    </ul>
                </Panel>
                : null}
            <Panel title={`Galaxy ${board.galaxy || ""}`.trim()}>
                <Form onSubmit={post} className="board-compose">
                    <Form.Control as="textarea" rows={3} value={draft} onChange={(e) => setDraft(e.target.value)}
                        placeholder="Write to your galaxy" aria-label="Post" />
                    <div className="form-actions">
                        {max ? <span className={"text-muted" + (length > max ? " text-danger" : "")}>{length}/{max}</span> : null}
                        <SubmitButton loading={props.loading.galaxyboard} blocked={blocked}>Post</SubmitButton>
                    </div>
                </Form>
                {posts.length === 0
                    ? <p className="text-muted board-empty">Nothing posted yet. Only kingdoms in your galaxy can read this board.</p>
                    : <ul className="board-posts">
                        {posts.map((item) => (
                            <Post key={item.id} post={item} kingdoms={kingdoms} mine={item.from === me}
                                canModerate={board.can_moderate} pinned={pinned?.id === item.id}
                                onPin={pinned?.id === item.id ? unpin : () => pin(item.id)} onDelete={() => remove(item.id)} />
                        ))}
                    </ul>}
            </Panel>
        </div>
    );
}

export default GalaxyBoard;
