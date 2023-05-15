import {useState} from "react";
import {
    useNavigate,
  } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import 'bootstrap/dist/css/bootstrap.css';
import "./signup.css"

function SignUp(props) {
    const navigate = useNavigate();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [message, setMessage] = useState("");
    const [created, setCreated] = useState(false);
    const [loading, setLoading] = useState(false);

    const parseSubmit = (r) => {
        if (r.status == "success") {
            setCreated(true);
        }
        setMessage(r.message);
    }
 
    const handleUsername = (e) => {
        setUsername(e.target.value);
    }
    const handlePassword = (e) => {
        setPassword(e.target.value);
    }
    const onClickSubmit = async () => {
        const opts = {
            "username": username,
            "password": password,
        };
        setLoading(true);
        fetch('api/signup', {
            method: 'POST',
            body: JSON.stringify(opts)
        }).then(
            r => r.json()
        ).then(r => parseSubmit(r))
        setLoading(false);
    };
    const onClickGoLogin = (e)=>{
        navigate("/login")
    }

    return (
        <div className="signup">
            <div className="signup-content">
                {
                    created
                    ? <>
                        <h2>Created!</h2>
                        <Button variant="primary" type="submit" onClick={onClickGoLogin}>Go to Login</Button>
                    </>
                    : <>
                        <h2>Create an accout</h2>
                        <InputGroup className="account-form">
                            <InputGroup.Text>
                                Username
                            </InputGroup.Text>
                            <Form.Control 
                                id="username"
                                name="username"
                                value={username} 
                                onChange={handleUsername}
                                placeholder=""
                                type="text"
                                autoComplete="off"
                            />
                        </InputGroup>
                        <InputGroup className="account-form">
                            <InputGroup.Text>
                                Password
                            </InputGroup.Text>
                            <Form.Control 
                                id="password"
                                name="password"
                                value={password} 
                                onChange={handlePassword}
                                placeholder=""
                                type="password"
                                autoComplete="new-password"
                            />
                        </InputGroup>
                        {
                            loading
                            ? <Button className="signup-button" variant="primary" type="submit" disabled>
                                Loading...
                            </Button>
                            : <Button className="signup-button" variant="primary" type="submit" onClick={onClickSubmit}>
                                Submit
                            </Button>
                        }
                        <span>{message}</span>
                    </>
                }
            </div>
        </div>
    )
}

export default SignUp;