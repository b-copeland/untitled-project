import {useState} from "react";
import "./navbar.css";
import {
    Link,
    useLocation,
    useNavigate,
  } from "react-router-dom";
import Button from 'react-bootstrap/Button';
import Nav from 'react-bootstrap/Nav';
import Offcanvas from 'react-bootstrap/Offcanvas';
import 'bootstrap/dist/css/bootstrap.css';
import { logout } from "../auth";
import { sections } from "../routes";

const bold = {"fontWeight": "bold"};

/**
 * The side navigation, built from the page table in routes.js: a bold link for each section (with a count of anything
 * new in it), and the section's own pages underneath while you are in it. Clicking a section link that is already open
 * (twice in a row) closes the menu on a phone.
 */
function SideNavbar(props) {
  const [lastSectionClicked, setLastSectionClicked] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();

  const closeNav = () => props.setShowNav(false);

  const onClickLogout = () => {
    logout();
    navigate('/login');
  };

  const onClickSection = (path) => {
    if (lastSectionClicked === path) {
      closeNav();
      setLastSectionClicked(null);
    } else {
      setLastSectionClicked(path);
    }
  };

  // " (3)" when there is something new in these categories, otherwise nothing.
  const newCount = (categories = []) => {
    const count = categories.reduce((total, category) => total + parseInt((props.notifs || {})[category] || 0), 0);
    return count > 0 ? ` (${count})` : "";
  };

  const sectionLink = (to, label, onClick) => (
    <Nav.Link as={Link} to={to} onClick={onClick} style={bold}>{label}</Nav.Link>
  );

  return (
    <Offcanvas className="nav-canvas" show={props.showNav} onHide={closeNav} responsive="lg" style={{minWidth: "300px"}}>
      <Offcanvas.Header closeButton />
      <Offcanvas.Body>
        <div className="navdiv">
          <Nav className="mainnav">
            {sectionLink("/", "Landing", () => onClickSection("/"))}
            {!props.logged ? <><br />{sectionLink("/login", "Login", () => onClickSection("/login"))}</> : null}
            {props.logged ? <>
              {sections.map((section) => {
                const open = section.pages.some((page) => page.path === location.pathname);
                return (
                  <div key={section.title}>
                    <br />
                    {sectionLink(section.path, section.title + newCount(section.notifs), () => onClickSection(section.path))}
                    {open ? section.pages.filter((page) => !page.hidden).map((page) => (
                      <Nav.Link key={page.path} as={Link} to={page.path} onClick={closeNav}>
                        &nbsp;&nbsp;{page.label}{newCount(page.notifs)}
                      </Nav.Link>
                    )) : null}
                  </div>
                );
              })}
              <br />
              {sectionLink("/help", "Help", () => onClickSection("/help"))}
            </> : null}
          </Nav>
          {props.logged ? <div className="nav-logout"><Button onClick={onClickLogout}>Logout</Button></div> : null}
        </div>
      </Offcanvas.Body>
    </Offcanvas>
  );
}

export default SideNavbar;
