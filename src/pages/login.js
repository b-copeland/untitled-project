import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Card from "react-bootstrap/Card";
import Form from "react-bootstrap/Form";
import Button from "react-bootstrap/Button";
import Alert from "react-bootstrap/Alert";
import 'bootstrap/dist/css/bootstrap.css';
import { login, logout } from "../auth";
import "./login.css";

function Login(props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const onSubmitClick = (e) => {
    e.preventDefault();
    setMessage("");
    setBusy(true);
    fetch('api/login', {
      method: 'post',
      body: JSON.stringify({ 'username': username, 'password': password }),
    }).then(r => r.json())
      .then(session => {
        if (session.accessToken) {
          login(session);
          navigate('/status');
        } else {
          setMessage("Invalid username or password");
        }
      })
      .catch(() => setMessage("Could not reach the server, try again"))
      .finally(() => setBusy(false));
  };

  return (
    <div className="login-page">
      <Card className="login-card">
        <Card.Body>
          <Card.Title as="h2" className="login-title">{props.logged ? "You are signed in" : "Sign in"}</Card.Title>
          {!props.logged ? <Form onSubmit={onSubmitClick}>
            <Form.Group className="mb-3" controlId="login-username">
              <Form.Label>Username</Form.Label>
              <Form.Control type="text" autoComplete="username" autoFocus
                onChange={(e) => setUsername(e.target.value)} value={username} />
            </Form.Group>
            <Form.Group className="mb-3" controlId="login-password">
              <Form.Label>Password</Form.Label>
              <Form.Control type="password" autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)} value={password} />
            </Form.Group>
            {message !== "" ? <Alert variant="danger" className="py-2">{message}</Alert> : null}
            <div className="d-grid">
              <Button type="submit" disabled={busy || username === "" || password === ""}>
                {busy ? "Signing in..." : "Sign in"}
              </Button>
            </div>
            <div className="login-links">
              <a href="/forgot">Forgot your password or username?</a>
              <Link to="/signup">Create an account</Link>
            </div>
          </Form>
          : <div className="d-grid"><Button variant="outline-secondary" onClick={() => logout()}>Sign out</Button></div>}
        </Card.Body>
      </Card>
    </div>
  );
}

export default Login;
