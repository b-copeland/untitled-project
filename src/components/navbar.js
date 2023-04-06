import {useState} from "react";
import "./navbar.css";
import {
    Link,
    useLocation,
    useNavigate,
  } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Navbar from 'react-bootstrap/Navbar';
import NavDropdown from 'react-bootstrap/NavDropdown';
import Offcanvas from 'react-bootstrap/Offcanvas';
import 'bootstrap/dist/css/bootstrap.css';
import { logout } from "../auth";
import {initGlobalData} from "../App"

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

function SideNavbar(props) {
  // const [show, setShow] = useState(props.showNav);

  const handleClose = () => props.setShowNav(false);
  const handleShow = () => props.setShowNav(true);
  let location = useLocation();
  const navigate = useNavigate();

  const pathname = location.pathname;

  const onClickLogout = () => {
    logout();
    navigate('/login');
    props.setData(initGlobalData);
  }
  return (
    <>
      {/* <Button variant="primary" className="d-lg-none" onClick={handleShow}>
        Launch
      </Button> */}
      <Offcanvas show={props.showNav} onHide={handleClose} responsive="lg" style={{minWidth: "385px"}}>
      <Offcanvas.Header closeButton />
      <Offcanvas.Body>
      <div className="navdiv">
        <Nav className="mainnav">
          <Nav.Link as={Link} to="/" style={{"fontWeight": "bold"}}>Landing</Nav.Link>
          {
            !props.logged
            ? <>
              <br />
              <Nav.Link as={Link} to="/login" style={{"fontWeight": "bold"}}>Login</Nav.Link>
            </>
            : null
          }
          {
            props.logged
            ? <>
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
            </>
            : null
          }
        </Nav>
        {
          props.logged
          ? <div className="nav-logout">
            <Button onClick={onClickLogout}>Logout</Button>
          </div>
          : null
        }
      </div>
      </Offcanvas.Body>
    </Offcanvas>
  </>
  );
}

export default SideNavbar;