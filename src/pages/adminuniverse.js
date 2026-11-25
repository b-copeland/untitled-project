import React, { useCallback, useEffect, useState } from "react";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Table from "react-bootstrap/Table";
import { adminAuth } from "../auth";
import { displayNumber } from "../format";

const REFRESH_SECONDS = 30;

// The admin's view of a round: every kingdom at a glance (four reads, whatever the number of kingdoms), and one
// kingdom in full when it is clicked. Admin only; everything is shown.
function AdminUniverse() {
  const [universe, setUniverse] = useState(null);
  const [error, setError] = useState("");
  const [galaxy, setGalaxy] = useState("");
  const [follow, setFollow] = useState(false);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);

  const load = useCallback(() => {
    adminAuth.authFetch("api/admin/universe").then(r => r.json()).then(r => {
      if (r.kingdoms) { setUniverse(r); setError(""); } else { setError(r.message || "Could not load the universe"); }
    }).catch(() => setError("Could not load the universe"));
  }, []);

  const open = useCallback((kdId) => {
    setSelected(kdId);
    adminAuth.authFetch(`api/admin/kingdom/${kdId}`).then(r => r.json()).then(r => setDetails(r.kingdom ? r : null));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!follow) return undefined;
    const timer = setInterval(() => { load(); if (selected) open(selected); }, REFRESH_SECONDS * 1000);
    return () => clearInterval(timer);
  }, [follow, selected, load, open]);

  if (error) return <p role="alert">{error}</p>;
  if (!universe) return <p>Loading the universe…</p>;

  const galaxies = [...new Set(universe.kingdoms.map(kd => kd.galaxy).filter(Boolean))].sort();
  const shown = universe.kingdoms.filter(kd => !galaxy || kd.galaxy === galaxy);
  return (
    <div className="admin-universe">
      <h3>Watch the round</h3>
      <div className="d-flex flex-wrap gap-3 align-items-center mb-2">
        <Form.Select aria-label="Galaxy" size="sm" style={{ maxWidth: "12rem" }} value={galaxy} onChange={e => setGalaxy(e.target.value)}>
          <option value="">All galaxies</option>
          {galaxies.map(g => <option key={g} value={g}>{g}</option>)}
        </Form.Select>
        <Form.Check type="switch" id="admin-follow" label={`Refresh every ${REFRESH_SECONDS} s`} checked={follow}
          onChange={e => setFollow(e.target.checked)} />
        <Button size="sm" variant="secondary" onClick={load}>Refresh now</Button>
      </div>
      <div style={{ overflowX: "auto" }}>
        <Table hover size="sm">
          <thead>
            <tr><th>#</th><th>Kingdom</th><th>Playstyle</th><th>Galaxy</th><th>Empire</th><th>Stars</th><th>Networth</th><th>Points</th></tr>
          </thead>
          <tbody>
            {shown.map((kd, i) => (
              <tr key={kd.kd_id} onClick={() => open(kd.kd_id)} style={{ cursor: "pointer" }}
                className={kd.kd_id === selected ? "table-active" : undefined}>
                <td>{i + 1}</td><td>{kd.name}</td><td>{kd.playstyle}</td><td>{kd.galaxy}</td><td>{kd.empire || ""}</td>
                <td>{displayNumber(kd.stars)}</td><td>{displayNumber(kd.networth)}</td><td>{kd.points}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      {details && <KingdomDetails details={details} />}
      {details && selected && <KingdomTools kdId={selected} details={details} onChanged={() => { open(selected); load(); }} />}
    </div>
  );
}

function KingdomDetails({ details }) {
  const kd = details.kingdom;
  const bot = kd.bot || null;
  const listed = (values) => Object.entries(values || {}).filter(([, v]) => v).map(([k, v]) => `${k} ${displayNumber(v)}`).join(", ");
  return (
    <div className="admin-kingdom">
      <h4>{kd.name}</h4>
      <p>
        {kd.race}, {kd.status}. Stars {displayNumber(kd.stars)}, networth {displayNumber(kd.networth)}, money {displayNumber(kd.money)},
        people {displayNumber(kd.population)}, drones {displayNumber(kd.drones)}, fuel {displayNumber(kd.fuel)}.
      </p>
      <p><strong>Units at home:</strong> {listed(kd.units)}</p>
      <p><strong>Generals out:</strong> {(kd.generals_out || []).length}</p>
      <p><strong>Structures:</strong> {listed(kd.structures)}</p>
      <p><strong>Projects done:</strong> {(kd.completed_projects || []).join(", ") || "none"}</p>
      {bot && (
        <>
          <p><strong>Bot:</strong> {bot.type}, {bot.phase || "not yet planned"} phase; style {JSON.stringify(bot.style || {})}</p>
          <h5>Decisions (newest first)</h5>
          <ul className="admin-bot-log">
            {[...(bot.log || [])].reverse().slice(0, 20).map((entry, i) => (
              <li key={i}><code>{entry.time}</code> <strong>{entry.kind}</strong>: {entry.why}{entry.outcome ? ` (${entry.outcome})` : ""}</li>
            ))}
          </ul>
          <details><summary>Memory</summary><pre>{JSON.stringify(bot.memory || {}, null, 1)}</pre></details>
        </>
      )}
      <h5>News</h5>
      <ul>{[...details.news].reverse().map((item, i) => <li key={i}><code>{item.time}</code> {item.news}</li>)}</ul>
    </div>
  );
}

// The admin's tools for the open kingdom (adminkingdoms.py): rename it, delete one of its messages or board posts, and
// clear fields from its document that kingdoms do not have.
function KingdomTools({ kdId, details, onChanged }) {
  const [name, setName] = useState("");
  const [result, setResult] = useState("");
  const act = (path, body) => adminAuth.authFetch(`api/admin/kingdom/${kdId}/${path}`, {
    method: "POST", body: JSON.stringify(body || {}),
  }).then(r => r.json()).then(r => { setResult(r.message || ""); if (r.status === "success") onChanged(); })
    .catch(() => setResult("That did not work. Try again."));
  const messages = details.messages || [];
  const posts = details.board_posts || [];
  const stray = details.stray_fields || [];
  return (
    <div className="admin-kingdom-tools">
      <h5>Tools</h5>
      {result && <p role="status">{result}</p>}
      <Form className="d-flex gap-2 mb-2" onSubmit={e => { e.preventDefault(); act("rename", { name }); }}>
        <Form.Control size="sm" style={{ maxWidth: "16rem" }} aria-label="New name" placeholder="New name" value={name}
          onChange={e => setName(e.target.value)} />
        <Button size="sm" type="submit" disabled={!name.trim()}>Rename</Button>
      </Form>
      <p>
        <strong>Fields kingdoms do not have:</strong> {stray.length ? stray.join(", ") : "none"}{" "}
        {stray.length > 0 && <Button size="sm" variant="warning" onClick={() => act("clearfields")}>Clear them</Button>}
      </p>
      <h6>Messages (newest first)</h6>
      {messages.length === 0 ? <p>None</p> : (
        <ul className="admin-messages">
          {messages.map((m, i) => (
            <li key={i}>
              <code>{m.time}</code> {m.from ? "to" : "from"} {m.with}: {m.message}{" "}
              <Button size="sm" variant="outline-danger" onClick={() => act("messages/delete", { message: m })}>Delete</Button>
            </li>
          ))}
        </ul>
      )}
      <h6>Galaxy board posts</h6>
      {posts.length === 0 ? <p>None</p> : (
        <ul className="admin-posts">
          {posts.map(post => (
            <li key={post.id}>
              <code>{post.time}</code> {post.text}{" "}
              <Button size="sm" variant="outline-danger" onClick={() => act(`board/${post.id}/delete`)}>Delete</Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AdminUniverse;
