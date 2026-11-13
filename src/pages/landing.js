import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';
import { GiCrossedSwords, GiMagnifyingGlass, GiSpaceship, GiBank } from "react-icons/gi";
import "./landing.css";

// The four playstyles from the game's design: what a player can do, in a line each.
const PLAYSTYLES = [
    { icon: GiSpaceship, title: "Explore", text: "Settle new stars and grow your kingdom faster than anyone else." },
    { icon: GiCrossedSwords, title: "Attack", text: "Train a fleet and take stars from the kingdoms around you." },
    { icon: GiMagnifyingGlass, title: "Spy", text: "Gather intel and share it, so your galaxy strikes with its eyes open." },
    { icon: GiBank, title: "Plunder", text: "Slip in, rob what others have stockpiled and slip out again." },
];

const formatDate = (value) => (value ? new Date(value).toLocaleString() : "...");

function Landing(props) {
    const [state, setState] = useState({});

    useEffect(() => {
        fetch('api/state', {keepalive: true}).then(r => r.json()).then(r => setState(r)).catch(
            err => console.log('Failed to fetch state', err)
        );
    }, []);

    return (
        <div className="landing">
            <section className="landing-hero">
                <h1>Untitled Space Game</h1>
                <p className="landing-tagline">
                    A long-running multiplayer strategy game in your browser. Run a kingdom, join a galaxy, and work
                    together to take control of the universe.
                </p>
                <div className="landing-buttons">
                    {props.logged
                        ? <Button as={Link} to="/status" size="lg">Go to your kingdom</Button>
                        : <>
                            <Button as={Link} to="/signup" size="lg">Sign up</Button>
                            <Button as={Link} to="/login" size="lg" variant="outline-primary">Sign in</Button>
                        </>}
                </div>
                <Link to="/help" className="landing-help-link">New here? Read how it works</Link>
            </section>

            <section className="landing-playstyles" aria-label="Ways to play">
                {PLAYSTYLES.map(({ icon: Icon, title, text }) => (
                    <Card key={title} className="landing-card">
                        <Card.Body>
                            <Icon className="landing-card-icon" aria-hidden="true" />
                            <Card.Title as="h2">{title}</Card.Title>
                            <Card.Text>{text}</Card.Text>
                        </Card.Body>
                    </Card>
                ))}
            </section>

            <section className="landing-round">
                <h2>The current round</h2>
                <dl>
                    <div><dt>Starts</dt><dd>{formatDate(state.state?.game_start)}</dd></div>
                    <div><dt>Ends</dt><dd>{formatDate(state.state?.game_end)}</dd></div>
                </dl>
                <p className="landing-note">One login every twelve hours with a good plan should keep you competitive.</p>
            </section>
        </div>
    );
}

export default Landing;
