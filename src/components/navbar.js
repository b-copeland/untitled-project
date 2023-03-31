import "./navbar.css";
import {
    Link,
    useLocation,
  } from "react-router-dom";
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Navbar from 'react-bootstrap/Navbar';
import NavDropdown from 'react-bootstrap/NavDropdown';
import 'bootstrap/dist/css/bootstrap.css';

const homePaths = [
  "/status",
  "/news",
  "/galaxy",
  "/forums",
  "/history",
];
const buildPaths = [
  "/build",
  "/settle",
  "/structures",
  "/military",
  "/projects",
  "/missiles",
]
const conquerPaths = [
  "/conquer",
  "/attack",
  "/spy",
  "/shareintel",
  "/launchmissiles",
  "/primitives",
]

const politicsPaths = [
  "/galaxypolitics",
  "/empirepolitics",
  "/universepolitics",
]

function BasicExample(props) {
  let location = useLocation();
  const pathname = location.pathname;
  console.log(homePaths.includes(pathname));
  return (
    <div className="sidenav">
      <Nav className="mainnav">
        <Nav.Link as={Link} to="/" style={{"fontWeight": "bold"}}>Landing</Nav.Link>
        <br />
        <Nav.Link as={Link} to="/login" style={{"fontWeight": "bold"}}>Login</Nav.Link>
        <br />
        <Nav.Link as={Link} to="/status" style={{"fontWeight": "bold"}}>Home</Nav.Link>
        {
          homePaths.includes(pathname)
          ? <>
            <Nav.Link as={Link} to="/news">&nbsp;&nbsp;News</Nav.Link>
            <Nav.Link as={Link} to="/galaxy">&nbsp;&nbsp;Galaxy</Nav.Link>
            <Nav.Link as={Link} to="/forums">&nbsp;&nbsp;Forums</Nav.Link>
            <Nav.Link as={Link} to="/history">&nbsp;&nbsp;History</Nav.Link>
          </>
          : null
        }
        <br />
        <Nav.Link as={Link} to="/build" style={{"fontWeight": "bold"}}>Build</Nav.Link>
        {
          buildPaths.includes(pathname)
          ? <>
            <Nav.Link as={Link} to="/settle">&nbsp;&nbsp;Settle</Nav.Link>
            <Nav.Link as={Link} to="/structures">&nbsp;&nbsp;Structures</Nav.Link>
            <Nav.Link as={Link} to="/military">&nbsp;&nbsp;Military</Nav.Link>
            <Nav.Link as={Link} to="/projects">&nbsp;&nbsp;Projects</Nav.Link>
            <Nav.Link as={Link} to="/missiles">&nbsp;&nbsp;Build Missiles</Nav.Link>
          </>
          : null
        }
        <br />
        <Nav.Link as={Link} to="/conquer" style={{"fontWeight": "bold"}}>Conquer</Nav.Link>
        {
          conquerPaths.includes(pathname)
          ? <>
            <Nav.Link as={Link} to="/attack">&nbsp;&nbsp;Attack</Nav.Link>
            <Nav.Link as={Link} to="/spy">&nbsp;&nbsp;Spy</Nav.Link>
            <Nav.Link as={Link} to="/shareintel">&nbsp;&nbsp;Share Intel</Nav.Link>
            <Nav.Link as={Link} to="/launchmissiles">&nbsp;&nbsp;Launch Missiles</Nav.Link>
            <Nav.Link as={Link} to="/primitives">&nbsp;&nbsp;Primitives</Nav.Link>
          </>
          : null
        }
        <br />
        <Nav.Link as={Link} to="/galaxypolitics" style={{"fontWeight": "bold"}}>Politics</Nav.Link>
        {
          politicsPaths.includes(pathname)
          ? <>
            <Nav.Link as={Link} to="/empirepolitics">&nbsp;&nbsp;Empire Politics</Nav.Link>
            <Nav.Link as={Link} to="/universepolitics">&nbsp;&nbsp;Universe Politics</Nav.Link>
          </>
          : null
        }
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