import React from "react";
import { Routes, Route, Navigate, Outlet, useLocation, useParams } from "react-router-dom";

import { useAuth, logout } from "./auth";
import { useGameData, initGlobalData } from "./data/gameData";
import { useNotifications, Notifications } from "./components/notifications";
import SideNavbar from "./components/navbar";
import UserMenu from "./components/usermenu";
import Button from 'react-bootstrap/Button';
import { FiMenu } from "react-icons/fi";
import 'bootstrap/dist/css/bootstrap.css';
import "./App.css";
import { publicRoutes, createKingdomRoute, gamePages, propsFor } from "./routes";
import Header from "./components/header";
import { PageContext, PageHead } from "./components/pagehead";
import { useTheme } from "./theme";
import { startVisitClock } from "./lastVisit";

/**
 * A game page in its frame: the header strip, then the page's section and title (or the way back to the page that
 * linked here), then the page. Links on the page learn where they are from PageContext.
 */
function GamePage({ route, context }) {
  const location = useLocation();
  const params = useParams();
  const title = route.title ? route.title(context.data, params) : route.label;
  const Page = route.component;
  return (
    <PageContext.Provider value={{ path: location.pathname + location.search, label: title }}>
      <Header data={context.data} />
      <PageHead section={route.section} title={title} />
      <Page {...propsFor(route, context)} />
    </PageContext.Provider>
  );
}

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
  const notifications = useNotifications({ logged, session, updateData, muted: data.preferences?.muted });
  useTheme(logged ? data.preferences : null);
  React.useEffect(() => { if (logged) startVisitClock(); }, [logged]);
  const context = { logged, session, data, loading, updateData };

  const renderPage = (route, extraProps) => {
    const Page = route.component;
    return <Page {...extraProps} />;
  };

  return (
    <div className="main">
      <div className="topbar d-lg-none">
        <Button variant="outline-secondary" aria-label="Open menu" onClick={() => setShowNav(true)}><FiMenu /></Button>
        <span className="topbar-title"><img src="/favicon.svg" alt="" className="topbar-logo" />Farsteel</span>
        {logged ? <UserMenu id="user-menu-phone" username={data.preferences?.username} /> : null}
      </div>

      <div className="main-body">
        <Notifications {...notifications} />
        <SideNavbar logged={logged} showNav={showNav} setShowNav={setShowNav} notifs={data.notifs} hasKingdom={hasKingdom(data.kingdomid)}
          kingdomName={data.kingdom?.name} galaxy={data.galaxies_inverted?.[data.kingdomid?.kd_id]}/>
        <div className="router">
          {logged ? <div className="userbar d-none d-lg-flex"><UserMenu username={data.preferences?.username} /></div> : null}
          <div className="router-body">
            <Routes>
              {/* Spending became a tab of Automation; old links and bookmarks land there. */}
              <Route path="/spending" element={<Navigate to="/automation?tab=spending" replace />} />
              {publicRoutes.map((route) => (
                <Route key={route.path} path={route.path}
                  element={renderPage(route, route.props ? route.props(context) : {})}/>
              ))}
              <Route path={createKingdomRoute.path} element={
                <NewKingdomRoute logged={logged} kingdomid={data.kingdomid}>
                  {renderPage(createKingdomRoute, createKingdomRoute.props(context))}
                </NewKingdomRoute>}/>
              <Route element={<ProtectedRoute logged={logged} session={session} kingdomid={data.kingdomid}/>}>
                {gamePages.map((route) => (
                  <Route key={route.path} path={route.path} element={<GamePage route={route} context={context}/>}/>
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
