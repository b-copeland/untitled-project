import "./navbar.css";
import {
    Link,
  } from "react-router-dom";

function BasicExample() {
  return (
    <nav>
        <ul className="nav-list">
            <li><Link to="/">Home</Link></li>
            <li><Link to="/login">Login</Link></li>
            <li><Link to="/status">Status</Link></li>
            <li><Link to="/news">News</Link></li>
            <li><Link to="/galaxy">Galaxy</Link></li>
            <li><Link to="/forums">Forums</Link></li>
            <li><Link to="/history">History</Link></li>
            <li><Link to="/build">Build</Link></li>
            <li><Link to="/settle">Settle</Link></li>
            <li><Link to="/structures">Structures</Link></li>
            <li><Link to="/military">Military</Link></li>
            <li><Link to="/projects">Projects</Link></li>
            <li><Link to="/missiles">Missiles</Link></li>
            <li><Link to="/conquer">Conquer</Link></li>
            <li><Link to="/attack">Attack</Link></li>
            <li><Link to="/spy">Spy</Link></li>
            <li><Link to="/launchmissiles">Launch Missiles</Link></li>
        </ul>
    </nav>
  );
}

export default BasicExample;