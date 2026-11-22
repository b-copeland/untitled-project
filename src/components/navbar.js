import {useEffect} from "react";
import "./navbar.css";
import {
    Link,
    useLocation,
  } from "react-router-dom";
import Nav from 'react-bootstrap/Nav';
import Offcanvas from 'react-bootstrap/Offcanvas';
import 'bootstrap/dist/css/bootstrap.css';
import { sections } from "../routes";

/**
 * The side navigation, built from the page table in routes.js: a label for each section (not a link; with a count of anything new in
 * it) and its pages, all links at one indent, underneath, then Misc (Help and Landing) last. Settings and Logout are in the
 * account menu (usermenu.js), not here. The list scrolls. From the lg breakpoint up it is a fixed column; below
 * that it is a drawer opened from the top bar, and it closes whenever you navigate.
 */
function SideNavbar(props) {
  const location = useLocation();

  const closeNav = () => props.setShowNav(false);
  useEffect(() => { props.setShowNav(false); }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  // " (3)" when there is something new in these categories, otherwise nothing.
  const newCount = (categories = []) => {
    const count = categories.reduce((total, category) => total + parseInt((props.notifs || {})[category] || 0), 0);
    return count > 0 ? ` (${count})` : "";
  };

  const sectionLink = (to, label) => (
    <Nav.Link as={Link} to={to} onClick={closeNav} className="nav-page" active={location.pathname === to}>{label}</Nav.Link>
  );

  return (
    <Offcanvas className="nav-canvas" show={props.showNav} onHide={closeNav} responsive="lg">
      <Offcanvas.Header closeButton><Offcanvas.Title>Menu</Offcanvas.Title></Offcanvas.Header>
      <Offcanvas.Body>
        <div className="navdiv">
          <Nav className="mainnav">
            {!props.logged ? <>{sectionLink("/login", "Login")}</> : null}
            {props.logged && !props.hasKingdom ? <>
              {sectionLink("/createkingdom", "Create your kingdom")}
            </> : null}
            {props.logged && props.hasKingdom ? <>
              {sections.map((section) => (
                <div key={section.title} className="nav-group">
                  <div className="nav-heading">{section.title}{newCount(section.notifs)}</div>
                  {section.pages.filter((page) => !page.hidden).map((page) => (
                    <Nav.Link key={page.path} as={Link} to={page.path} onClick={closeNav} className="nav-page" active={location.pathname === page.path}>
                      {page.label}{newCount(page.notifs)}
                    </Nav.Link>
                  ))}
                </div>
              ))}
            </> : null}
            <div className="nav-group">
              <div className="nav-heading">Misc</div>
              {sectionLink("/help", "Help")}
              {sectionLink("/", "Landing")}
            </div>
          </Nav>
        </div>
      </Offcanvas.Body>
    </Offcanvas>
  );
}

export default SideNavbar;
