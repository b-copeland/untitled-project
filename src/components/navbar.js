import {useEffect} from "react";
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

/**
 * The side navigation, built from the page table in routes.js: a link for each section (with a count of anything new in
 * it), and the section's own pages underneath while you are in it. From the lg breakpoint up it is a fixed column; below
 * that it is a drawer opened from the top bar, and it closes whenever you navigate.
 */
function SideNavbar(props) {
  const location = useLocation();
  const navigate = useNavigate();

  const closeNav = () => props.setShowNav(false);
  useEffect(() => { props.setShowNav(false); }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  const onClickLogout = () => {
    logout();
    navigate('/login');
  };

  // " (3)" when there is something new in these categories, otherwise nothing.
  const newCount = (categories = []) => {
    const count = categories.reduce((total, category) => total + parseInt((props.notifs || {})[category] || 0), 0);
    return count > 0 ? ` (${count})` : "";
  };

  const sectionLink = (to, label) => (
    <Nav.Link as={Link} to={to} className="nav-section" active={location.pathname === to}>{label}</Nav.Link>
  );

  return (
    <Offcanvas className="nav-canvas" show={props.showNav} onHide={closeNav} responsive="lg">
      <Offcanvas.Header closeButton><Offcanvas.Title>Menu</Offcanvas.Title></Offcanvas.Header>
      <Offcanvas.Body>
        <div className="navdiv">
          <Nav className="mainnav">
            {sectionLink("/", "Landing")}
            {!props.logged ? <>{sectionLink("/login", "Login")}</> : null}
            {props.logged ? <>
              {sections.map((section) => {
                const open = section.pages.some((page) => page.path === location.pathname);
                return (
                  <div key={section.title}>
                    
                    {sectionLink(section.path, section.title + newCount(section.notifs))}
                    {open ? section.pages.filter((page) => !page.hidden).map((page) => (
                      <Nav.Link key={page.path} as={Link} to={page.path} className="nav-page" active={location.pathname === page.path}>
                        {page.label}{newCount(page.notifs)}
                      </Nav.Link>
                    )) : null}
                  </div>
                );
              })}
              
              {sectionLink("/help", "Help")}
            </> : null}
          </Nav>
          {props.logged ? <div className="nav-logout"><Button onClick={onClickLogout}>Logout</Button></div> : null}
        </div>
      </Offcanvas.Body>
    </Offcanvas>
  );
}

export default SideNavbar;
