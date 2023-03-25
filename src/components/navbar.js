import "./navbar.css";
import {
    Link,
  } from "react-router-dom";
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Navbar from 'react-bootstrap/Navbar';
import NavDropdown from 'react-bootstrap/NavDropdown';
import 'bootstrap/dist/css/bootstrap.css';

function BasicExample() {
  return (
    <div className="sidenav">
      <Nav className="mainnav">
        <Nav.Link as={Link} to="/">Landing</Nav.Link>
        <Nav.Link as={Link} to="/login">Login</Nav.Link>
        <Nav.Link as={Link} to="/status">Status</Nav.Link>
        <Nav.Link as={Link} to="/news">News</Nav.Link>
        <Nav.Link as={Link} to="/galaxy">Galaxy</Nav.Link>
        <Nav.Link as={Link} to="/forums">Forums</Nav.Link>
        <Nav.Link as={Link} to="/history">History</Nav.Link>
        <Nav.Link as={Link} to="/build">Build</Nav.Link>
        <Nav.Link as={Link} to="/settle">Settle</Nav.Link>
        <Nav.Link as={Link} to="/structures">Structures</Nav.Link>
        <Nav.Link as={Link} to="/military">Military</Nav.Link>
        <Nav.Link as={Link} to="/projects">Projects</Nav.Link>
        <Nav.Link as={Link} to="/missiles">Build Missiles</Nav.Link>
        <Nav.Link as={Link} to="/conquer">Conquer</Nav.Link>
        <Nav.Link as={Link} to="/attack">Attack</Nav.Link>
        <Nav.Link as={Link} to="/spy">Spy</Nav.Link>
        <Nav.Link as={Link} to="/shareintel">Share Intel</Nav.Link>
        <Nav.Link as={Link} to="/launchmissiles">Launch Missiles</Nav.Link>
        <Nav.Link as={Link} to="/primitives">Primitives</Nav.Link>
      </Nav>
    </div>
  );
}

function BasicExample2() {
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
            <li><Link to="/shareintel">Share Intel</Link></li>
            <li><Link to="/launchmissiles">Launch Missiles</Link></li>
        </ul>
    </nav>
  );
}

export default BasicExample;