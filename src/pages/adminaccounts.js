import React, { useCallback, useEffect, useState } from "react";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import Modal from "react-bootstrap/Modal";
import { adminAuth } from "../auth";
import { GameTable } from "../components/gametable";
import { ResultToasts, safeJson } from "../components/results";
import { showTime } from "./adminround";

// The admin's accounts tools (docs/admin.md#accounts): every account, the accounts it shares a login address or
// device with, setting its password, and banning or unbanning it. Admin only; one request for the list.

/** "address", "device" or "address and device": what two accounts were seen sharing. */
export const sharedBy = (share) => [share.ip ? "address" : null, share.device ? "device" : null].filter(Boolean).join(" and ");

/** The accounts the filters keep: by name, kingdom or email, bots only if asked, and only those sharing if asked. */
export function filterAccounts(accounts, { text = "", bots = false, sharedOnly = false, bannedOnly = false }) {
    const needle = text.trim().toLowerCase();
    return accounts.filter((account) => (bots || !account.bot)
        && (!sharedOnly || account.shares.length > 0)
        && (!bannedOnly || account.banned)
        && (!needle || [account.username, account.kingdom, account.email].some((value) => String(value || "").toLowerCase().includes(needle))));
}

function ManageAccount({ account, send, onClose }) {
    const [password, setPassword] = useState("");
    const [reason, setReason] = useState(account.ban_reason || "");
    const url = `api/admin/accounts/${account.id}`;
    return (
        <Modal show onHide={onClose} animation={false}>
            <Modal.Header closeButton><Modal.Title>{account.username}</Modal.Title></Modal.Header>
            <Modal.Body>
                <Form onSubmit={(e) => { e.preventDefault(); send(`${url}/password`, { password }).then(() => setPassword("")); }}>
                    <Form.Label htmlFor="admin-new-password">New password</Form.Label>
                    <div className="d-flex gap-2 mb-1">
                        <Form.Control id="admin-new-password" type="text" autoComplete="off" value={password}
                            onChange={(e) => setPassword(e.target.value)} />
                        <Button type="submit" disabled={password === ""}>Set</Button>
                    </div>
                    <Form.Text>Tell the player the new password yourself. A login token they already have keeps working.</Form.Text>
                </Form>
                <hr />
                {account.admin ? <p className="mb-0">An admin account can not be banned here.</p> : (
                    <Form onSubmit={(e) => { e.preventDefault(); send(`${url}/ban`, { reason }); }}>
                        <Form.Label htmlFor="admin-ban-reason">{account.banned ? "Banned" : "Ban"}{account.banned && account.banned_at ? ` since ${showTime(account.banned_at)}` : ""}</Form.Label>
                        <Form.Control id="admin-ban-reason" className="mb-1" type="text" maxLength={200} placeholder="Reason (the player sees it)"
                            value={reason} onChange={(e) => setReason(e.target.value)} />
                        <Form.Text className="d-block mb-2">They can not log in again, and are signed out within a day when their token expires. Their kingdom stays.</Form.Text>
                        <div className="form-actions">
                            {account.banned ? <Button variant="secondary" onClick={() => send(`${url}/unban`)}>Unban</Button> : null}
                            <Button type="submit" variant="danger">{account.banned ? "Change the reason" : "Ban"}</Button>
                        </div>
                    </Form>
                )}
            </Modal.Body>
        </Modal>
    );
}

function AdminAccounts() {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const [filters, setFilters] = useState({ text: "", bots: false, sharedOnly: false, bannedOnly: false });
    const [managing, setManaging] = useState(null);
    const [results, setResults] = useState([]);

    const load = useCallback(() => {
        adminAuth.authFetch("api/admin/accounts").then(safeJson).then((r) => {
            if (r.accounts) { setData(r); setError(""); } else { setError(r.message || "Could not load the accounts"); }
        }).catch(() => setError("Could not load the accounts"));
    }, []);
    useEffect(() => { load(); }, [load]);

    const send = useCallback((url, body) => adminAuth.authFetch(url, {
        method: "POST",
        body: body === undefined ? undefined : JSON.stringify(body),
    }).then(safeJson).then((result) => {
        setResults((previous) => previous.concat(result));
        load();
        return result;
    }), [load]);

    if (error) return <p role="alert">{error}</p>;
    if (!data) return <p>Loading the accounts…</p>;

    const byId = Object.fromEntries(data.accounts.map((account) => [account.id, account]));
    const shown = filterAccounts(data.accounts, filters);
    const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
    const columns = [
        {
            header: "Account", align: "left", cell: (a) => (
                <Button variant="link" className="p-0 text-start" onClick={() => setManaging(a.id)}>
                    {a.username}{a.admin ? " (admin)" : ""}{a.bot ? " (bot)" : ""}
                </Button>
            ),
        },
        { header: "Status", align: "left", cell: (a) => (a.banned ? <span className="text-danger" title={a.ban_reason}>Banned</span> : "Active") },
        {
            header: "Shares with", align: "left", cell: (a) => (a.shares.length === 0 ? "nobody" : a.shares.map((share) => (
                <div key={share.id} className="text-nowrap">
                    <Button variant="link" className="p-0 align-baseline" onClick={() => setManaging(share.id)}>{share.username}</Button>
                    {` (${sharedBy(share)})`}
                </div>
            ))),
        },
        { header: "Kingdom", align: "left", cell: (a) => a.kingdom || (a.kd_id ? `#${a.kd_id}` : "none") },
        { header: "Last login", align: "left", cell: (a) => (a.last_login ? showTime(a.last_login) : "not recorded") },
        { header: "Email", align: "left", cell: (a) => (a.email ? `${a.email}${a.email_verified ? "" : " (not confirmed)"}` : "none") },
    ];
    return (
        <div className="admin-accounts">
            <h3>Accounts</h3>
            <p className="text-muted small">
                Accounts that logged in from the same address or the same browser in the last {data.seen_days} days are listed together.
                A shared address can be a household, a school or a phone network: it is a reason to look, not proof.
            </p>
            <div className="d-flex flex-wrap gap-3 align-items-center mb-2">
                <Form.Control size="sm" style={{ maxWidth: "16rem" }} placeholder="Name, kingdom or email" aria-label="Search accounts"
                    value={filters.text} onChange={set("text")} />
                <Form.Check type="switch" id="accounts-shared" label="Sharing only" checked={filters.sharedOnly} onChange={set("sharedOnly")} />
                <Form.Check type="switch" id="accounts-banned" label="Banned only" checked={filters.bannedOnly} onChange={set("bannedOnly")} />
                <Form.Check type="switch" id="accounts-bots" label="Show bots" checked={filters.bots} onChange={set("bots")} />
                <Button size="sm" variant="secondary" onClick={load}>Refresh now</Button>
            </div>
            <p className="small mb-1">{shown.length} of {data.accounts.length} accounts</p>
            <GameTable columns={columns} rows={shown} rowKey={(a) => a.id} />
            {managing !== null && byId[managing] ? <ManageAccount key={managing} account={byId[managing]} send={send} onClose={() => setManaging(null)} /> : null}
            <ResultToasts title="Accounts" results={results} setResults={setResults} />
        </div>
    );
}

export default AdminAccounts;
