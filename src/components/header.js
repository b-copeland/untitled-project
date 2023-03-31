import React from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../auth";

class Clock extends React.Component {
constructor(props) {
    super(props);
    this.state = {
    date: new Date(),
    };
}

async componentDidMount() {
    const serverstart = await authFetch('/api/time').then(r => r.json());
    this.timerID = setInterval(
    () => this.tick(),
    this.props.interval
    );
    this.setState({
    start: Date.now(),
    serverstart: new Date(serverstart),
    })
}

componentWillUnmount() {
    clearInterval(this.timerID);
}

tick() {
    this.setState({
    date: new Date(this.state.serverstart?.getTime() + (Date.now() - this.state.start))
    });
}

render() {
    return (
    <span>Time: {this.state.date.toLocaleTimeString()}</span>
    );
}
}

function Header(props) {
if (Object.keys(props.data?.kingdom).length === 0) {
    return null;
}

const kdInfo = props.data.kingdom;
return (
    <div className="header-container">
    <div className="header-contents">
        <div className="header-item">
        <Clock interval={1000}/>
        </div>
        <div className="header-item">
        <span>Stars: {kdInfo.stars?.toLocaleString()}</span>
        </div>
        <div className="header-item">
        <span>Fuel: {Math.floor(kdInfo.fuel).toLocaleString()}</span>
        </div>
        <div className="header-item">
        <span>Pop: {Math.floor(kdInfo.population).toLocaleString()}</span>
        </div>
        <div className="header-item">
        <span>Money: {Math.floor(kdInfo.money).toLocaleString()}</span>
        </div>
        <div className="header-item">
        <span>Score: {Math.floor(kdInfo.score).toLocaleString()}</span>
        </div>
        <div className="header-item">
        <span>Spy Attempts: {kdInfo.spy_attempts}</span>
        </div>
        <div className="header-item">
        <span>Generals: {kdInfo.generals_available}</span>
        </div>
    </div>
    </div>
)
}

export default Header;