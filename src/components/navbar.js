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
        </ul>
    </nav>
  );
}

export default BasicExample;