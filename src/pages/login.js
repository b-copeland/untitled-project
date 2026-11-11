import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, logout } from "../auth";

function Login(props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  const onSubmitClick = (e) => {
    setMessage("");
    e.preventDefault();
    fetch('api/login', {
      method: 'post',
      body: JSON.stringify({ 'username': username, 'password': password }),
    }).then(r => r.json())
      .then(session => {
        if (session.accessToken) {
          login(session);
          navigate('/status');
        } else {
          setMessage("Invalid username/password");
        }
      });
  };

  return (
    <div>
      <h2>Login</h2>
      {!props.logged ? <form action="#">
        <div>
          <input type="text"
            placeholder="Username"
            onChange={(e) => setUsername(e.target.value)}
            value={username}
          />
        </div>
        <div>
          <input
            type="password"
            placeholder="Password"
            onChange={(e) => setPassword(e.target.value)}
            value={password}
            autoComplete="current-password"
          />
        </div>
        <button onClick={onSubmitClick} type="submit">
          Login
        </button>
        {message !== "" ? <h2>{message}</h2> : null}
        <div><a href="/forgot">Forgot your password or username?</a></div>
      </form>
      : <button onClick={() => logout()}>Logout</button>}
    </div>
  );
}

export default Login;
