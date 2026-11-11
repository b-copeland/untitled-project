import React from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";

import { useAuth, logout } from "./auth";
import { useGameData, initGlobalData } from "./data/gameData";
import { useNotifications, Notifications } from "./components/notifications";
import SideNavbar from "./components/navbar";
import Button from 'react-bootstrap/Button';
import 'bootstrap/dist/css/bootstrap.css';
import "./App.css";
import { sections, publicRoutes, createKingdomRoute, propsFor } from "./routes";

/**
 * Wraps the pages that need a player: a signed-in one (otherwise to the login page) who has made a kingdom (otherwise
 * to the page where they make it).
 */
const ProtectedRoute = ({ logged, session, kingdomid, redirectPath = '/login' }) => {
  if (session != null && session.hasOwnProperty("error")) {
    logout();
    return <Navigate to={redirectPath} replace />;
  }
  if (!logged) {
    return <Navigate to={redirectPath} replace />;
  }
  if (kingdomid.kd_id === undefined) {
    return <h2>Loading...</h2>;
  }
  if (kingdomid.kd_id === "" || kingdomid.created === false) {
    return <Navigate to="/createkingdom" replace />;
  }
  return <Outlet />;
};

function Content({ logged, session }) {
  const [showNav, setShowNav] = React.useState(false);
  const { data, loading, updateData } = useGameData({ logged });
  const notifications = useNotifications({ logged, session, updateData });
  const context = { logged, session, data, loading, updateData };

  const renderPage = (route, extraProps) => {
    const Page = route.component;
    return <Page {...extraProps} />;
  };

  return (
    <div className="main">
      <div className="d-lg-none nav-button">
        <Button variant="primary" type="submit" onClick={() => setShowNav(true)}>Nav</Button>
      </div>

      <div className="row main-body">
        <Notifications {...notifications} />
        <SideNavbar logged={logged} showNav={showNav} setShowNav={setShowNav} notifs={data.notifs}/>
        <div className="router">
          <div className="router-body">
            <Routes>
              {publicRoutes.map((route) => (
                <Route key={route.path} path={route.path}
                  element={renderPage(route, route.props ? route.props(context) : {})}/>
              ))}
              <Route path={createKingdomRoute.path}
                element={renderPage(createKingdomRoute, createKingdomRoute.props(context))}/>
              <Route element={<ProtectedRoute logged={logged} session={session} kingdomid={data.kingdomid}/>}>
                {sections.flatMap((section) => section.pages).map((route) => (
                  <Route key={route.path} path={route.path} element={renderPage(route, propsFor(route, context))}/>
                ))}
              </Route>
            </Routes>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [logged, session] = useAuth();

  if (session === null) {
    if (!!JSON.parse(localStorage.getItem("DOMNUS_GAME_TOKEN"))) {
      return null;
    }
  }
  return <Content logged={logged} session={session}/>;
}

export {App, initGlobalData};
