import React, { useEffect, useState } from "react";
import {useNavigate} from "react-router-dom";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";
import Button from 'react-bootstrap/Button';
import "./landing.css";

function Landing(props) {
    const navigate = useNavigate();
    const [state, setState] = useState({});

    useEffect(() => {
        const fetchData = () => {
            fetch('api/state', {keepalive: true}).then(
                r => r.json()
            ).then(r => setState(r)).catch(
                err => {
                    console.log('Failed to fetch state');
                    console.log(err);
                }
            );
        }
        fetchData();
    }, []);

    const onClickSignUp = (e)=>{
        navigate("/signup")
    }
    const onClickLogin = (e)=>{
        navigate("/login")
    }
    const onClickHelp = (e)=>{
        navigate("/help")
    }
    return (
        <div className="landing">
            <div className="landing-content">
                <h1 style={{textAlign: "center"}}>Welcome to<br/> Untitled Space Game!</h1>
                <br />
                <span>This is an early-access, multiplayer, text-based strategy game in which you work together with your galaxy to take control of the universe.</span>
                <div className="landing-buttons">
                    <Button className="landing-button" variant="primary" type="submit" onClick={onClickSignUp}>Sign Up</Button>
                    <Button className="landing-button" variant="primary" type="submit" onClick={onClickLogin}>Login</Button>
                    <Button className="landing-button" variant="primary" type="submit" onClick={onClickHelp}>Help</Button>
                </div>
                <div className="current-game-info">
                    <h3>Current Game Info</h3>
                    <div className="text-box">
                        <div className="text-box-item landing-page-item">
                            <span className="text-box-item-title">Game Start</span>
                            <span className="text-box-item-value">{new Date(state.state?.game_start).toLocaleString()}</span>
                        </div>
                        <div className="text-box-item landing-page-item">
                            <span className="text-box-item-title">Game End</span>
                            <span className="text-box-item-value">{new Date(state.state?.game_end).toLocaleString()}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Landing;