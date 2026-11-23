import React, { useCallback, useState } from "react";
import Button from "react-bootstrap/Button";
import Form from "react-bootstrap/Form";
import { adminAuth } from "../auth";
import { Panel } from "../components/planner";
import AdminRound from "./adminround";
import AdminUniverse from "./adminuniverse";
import AdminAccounts from "./adminaccounts";

// The admin page: sign in with an account that has the admin role, then run the round and watch it. See docs/admin.md.
function Admin() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [changes, setChanges] = useState(0);  // the watch list starts again after each admin action
  const changed = useCallback(() => setChanges((n) => n + 1), []);
  const [adminLogged] = adminAuth.useAuth();

  const onSubmitLogin = (e) => {
    e.preventDefault();
    fetch("/api/adminlogin", {
      method: "post",
      body: JSON.stringify({ username, password }),
    }).then((r) => r.json().catch(() => ({})))
      .then((session) => {
        if (session.accessToken) {
          adminAuth.login(session);
          setLoginError("");
        } else {
          setLoginError(session.message || "Wrong username or password, or not an admin");
        }
      })
      .catch(() => setLoginError("Could not reach the server"));
  };

  if (!adminLogged) {
    return (
      <div className="admin-page">
        <h2>Admin</h2>
        <Panel title="Sign in">
          <Form onSubmit={onSubmitLogin}>
            <Form.Control className="mb-2" type="text" placeholder="Username" aria-label="Username" autoComplete="username"
              onChange={(e) => setUsername(e.target.value)} value={username} />
            <Form.Control className="mb-2" type="password" placeholder="Password" aria-label="Password" autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)} value={password} />
            {loginError ? <p className="text-danger" role="alert">{loginError}</p> : null}
            <div className="form-actions"><Button type="submit">Sign in</Button></div>
          </Form>
        </Panel>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="d-flex justify-content-between align-items-center mb-2">
        <h2 className="mb-0">Admin</h2>
        <Button size="sm" variant="secondary" onClick={() => adminAuth.logout()}>Sign out</Button>
      </div>
      <AdminRound onChange={changed} />
      <hr />
      <AdminUniverse key={changes} />
      <hr />
      <AdminAccounts />
    </div>
  );
}

export default Admin;
