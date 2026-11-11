import {useEffect, useState} from "react";
import {useNavigate, useSearchParams} from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import 'bootstrap/dist/css/bootstrap.css';
import "./signup.css";

// Account recovery by email: ask for a reset link or a username reminder, choose a new password from the link, and
// confirm an address from the link sent when it was added. The server gives the same answer whether or not an
// address is known, so these pages say "if that address belongs to an account" and nothing more.

const postJson = (path, body) => fetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
}).then(r => r.json());

function ForgotAccount() {
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [message, setMessage] = useState("");
    const [loading, setLoading] = useState(false);

    const send = (path) => {
        setLoading(true);
        postJson(path, {email: email})
            .then(r => setMessage(r.message))
            .catch(() => setMessage("Something went wrong. Please try again."))
            .finally(() => setLoading(false));
    };

    return (
        <div className="signup">
            <div className="signup-content">
                <h2>Recover your account</h2>
                <span>Enter the email address on your account. It must have been confirmed.</span>
                <InputGroup className="account-form">
                    <InputGroup.Text>Email</InputGroup.Text>
                    <Form.Control
                        id="email"
                        name="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        type="email"
                        autoComplete="email"
                    />
                </InputGroup>
                <Button className="signup-button" variant="primary" disabled={loading || email === ""}
                    onClick={() => send('api/account/forgot-password')}>
                    Email me a password reset link
                </Button>
                <Button className="signup-button" variant="secondary" disabled={loading || email === ""}
                    onClick={() => send('api/account/forgot-username')}>
                    Remind me of my username
                </Button>
                <span>{message}</span>
                <Button className="signup-button" variant="link" onClick={() => navigate("/login")}>Back to login</Button>
            </div>
        </div>
    );
}

function ResetPassword() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [password, setPassword] = useState("");
    const [message, setMessage] = useState("");
    const [done, setDone] = useState(false);

    const submit = () => {
        postJson('api/account/reset-password', {token: searchParams.get("token"), password: password})
            .then(r => {
                setDone(r.status === "success");
                setMessage(r.message);
            })
            .catch(() => setMessage("Something went wrong. Please try again."));
    };

    return (
        <div className="signup">
            <div className="signup-content">
                <h2>Choose a new password</h2>
                {
                    done
                    ? <>
                        <span>{message}</span>
                        <Button className="signup-button" variant="primary" onClick={() => navigate("/login")}>Go to Login</Button>
                    </>
                    : <>
                        <InputGroup className="account-form">
                            <InputGroup.Text>New password</InputGroup.Text>
                            <Form.Control
                                id="password"
                                name="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                type="password"
                                autoComplete="new-password"
                            />
                        </InputGroup>
                        <Button className="signup-button" variant="primary" disabled={password === ""} onClick={submit}>
                            Change password
                        </Button>
                        <span>{message}</span>
                    </>
                }
            </div>
        </div>
    );
}

function VerifyEmail() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [message, setMessage] = useState("Confirming your email address...");

    useEffect(() => {
        postJson('api/account/email/verify', {token: searchParams.get("token")})
            .then(r => setMessage(r.message))
            .catch(() => setMessage("Something went wrong. Please try again."));
    }, [searchParams]);

    return (
        <div className="signup">
            <div className="signup-content">
                <h2>Email address</h2>
                <span>{message}</span>
                <Button className="signup-button" variant="primary" onClick={() => navigate("/login")}>Go to Login</Button>
            </div>
        </div>
    );
}

export {ForgotAccount, ResetPassword, VerifyEmail};
