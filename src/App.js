import React from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";

import { useAuth, logout } from "./auth";
import { useGameData, initGlobalData } from "./data/gameData";
import { useNotifications, Notifications } from "./components/notifications";
import SideNavbar from "./components/navbar";
import Button from 'react-bootstrap/Button';
import { FiMenu } from "react-icons/fi";
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
  if (!hasKingdom(kingdomid)) {
    return <Navigate to="/createkingdom" replace />;
  }
  return <Outlet />;
};

/** True once the player has a kingdom that is set up and playable. */
const hasKingdom = (kingdomid) => Boolean(kingdomid.kd_id) && kingdomid.created !== false;

/**
 * Wraps the page where a new player makes their kingdom: only for a signed-in player who does not have one yet. Anyone
 * else is sent where they belong (the login page, or the game).
 */
const NewKingdomRoute = ({ logged, kingdomid, children }) => {
  if (!logged) {
    return <Navigate to="/login" replace />;
  }
  if (kingdomid.kd_id === undefined) {
    return <h2>Loading...</h2>;
  }
  if (hasKingdom(kingdomid)) {
    return <Navigate to="/status" replace />;
  }
  return children;
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
      <div className="topbar d-lg-none">
        <Button variant="outline-secondary" aria-label="Open menu" onClick={() => setShowNav(true)}><FiMenu /></Button>
        <span className="topbar-title">Untitled Project</span>
      </div>

      <div className="main-body">
        <Notifications {...notifications} />
        <SideNavbar logged={logged} showNav={showNav} setShowNav={setShowNav} notifs={data.notifs} hasKingdom={hasKingdom(data.kingdomid)}/>
        <div className="router">
          <div className="router-body">
            <Routes>
              {publicRoutes.map((route) => (
                <Route key={route.path} path={route.path}
                  element={renderPage(route, route.props ? route.props(context) : {})}/>
              ))}
              <Route path={createKingdomRoute.path} element={
                <NewKingdomRoute logged={logged} kingdomid={data.kingdomid}>
                  {renderPage(createKingdomRoute, createKingdomRoute.props(context))}
                </NewKingdomRoute>}/>
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
