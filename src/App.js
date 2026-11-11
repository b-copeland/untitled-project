import React, { useEffect, useState, useRef } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link,
  Outlet,
  useSearchParams,
  useNavigate,
  redirect,
} from "react-router-dom";
import useWebSocket, { ReadyState } from 'react-use-websocket';
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "./auth";
import { useGameData, initGlobalData } from "./data/gameData";
import Button from 'react-bootstrap/Button';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import SideNavbar from "./components/navbar";
import 'bootstrap/dist/css/bootstrap.css';
import "./App.css";
import Admin from "./pages/admin.js";
import Landing from "./pages/landing.js";
import SignUp from "./pages/signup.js";
import {ForgotAccount, ResetPassword, VerifyEmail} from "./pages/recovery.js";
import CreateKingdom from "./pages/createkingdom.js";
import StatusContent from "./pages/home/status.js";
import NewsContent from "./pages/home/news.js";
import Galaxy from "./pages/galaxy.js";
import Message from "./pages/message.js";
import Forums from "./pages/home/forums.js";
import Scores from "./pages/home/scores.js";
import History from "./pages/home/history.js";
import Build from "./pages/build/build.js";
import Settle from "./pages/build/settle.js";
import Structures from "./pages/build/structures.js";
import MilitaryContent from "./pages/build/military.js";
import ProjectsContent from "./pages/build/projects.js";
import Missiles from "./pages/build/missiles.js";
import ConquerContent from "./pages/conquer/conquer.js";
import Attack from "./pages/conquer/attack.js";
import Spy from "./pages/conquer/spy.js";
import ShareIntel from "./pages/conquer/shareintel.js";
import LaunchMissiles from "./pages/conquer/launchmissiles.js";
import Schedule from "./pages/conquer/schedule.js";
import Primitives from "./pages/conquer/primitives.js";
import GalaxyPolitics from "./pages/politics/galaxypolitics.js";
import EmpirePolitics from "./pages/politics/empirepolitics.js";
import UniversePolitics from "./pages/politics/universepolitics.js";
import Help from "./pages/help/help.js";


const ProtectedRoute = ({ logged, session, kingdomid, redirectPath = '/login', children }) => {
  if (session != null && session.hasOwnProperty("error")) {
    logout();
    return <Navigate to={redirectPath} replace />;
  }
  if (!logged) {
    return <Navigate to={redirectPath} replace />;
  }

  if (kingdomid.kd_id === undefined) {
    return <h2>Loading...</h2>
  }

  if (kingdomid.kd_id === "" || kingdomid.created === false) {
    // console.log("Going to /createkingdom")
    return <Navigate to="/createkingdom" replace />;
  }

  return children ? children : <Outlet />;
};

function useInterval(callback, delay) {
  const savedCallback = useRef();

  // Remember the latest callback.
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  // Set up the interval.
  useEffect(() => {
    function tick() {
      savedCallback.current();
    }
    if (delay !== null) {
      let id = setInterval(tick, delay);
      return () => clearInterval(id);
    }
  }, [delay]);
}

function Content(props) {
  const hostname = window.location.hostname;
  const port = hostname === 'localhost' ? ':8000' : ''
  const protocolPrefix = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const [socketUrl, setSocketUrl] = useState(protocolPrefix + '//' + hostname + port + '/ws/listen');
  const [messageHistory, setMessageHistory] = useState([]);
  const { sendMessage, lastMessage, readyState } = useWebSocket(socketUrl);
  const { data, loading, updateData } = useGameData({ logged: props.logged });
  const [showNav, setShowNav] = useState(false);


  useEffect(() => {
    if (lastMessage !== null) {
      const jsonMessage = JSON.parse(lastMessage.data);
      if ((jsonMessage.update || []).length > 0) {
        updateData(jsonMessage.update);
      }
      setMessageHistory((prev) => [lastMessage, ...prev.slice(0, 9)]);
    }
  }, [lastMessage, setMessageHistory]);

  useEffect(() => {
    if (props.logged) {
      sendMessage(
        JSON.stringify({
          "jwt": props.session.accessToken,
        })
      );
    }
  }, [props.logged])

  useInterval(() => {
    sendMessage(
      JSON.stringify({
        "jwt": props.session.accessToken,
      })
    );
  }, 60000)

  const handleShowNav = () => {
    setShowNav(true);
  }

  const toasts = messageHistory.map((message, index) => {
    const jsonMessage = JSON.parse(message.data);
    return <Toast
        key={index}
        onClose={(e) => setMessageHistory(messageHistory.slice(0, index).concat(messageHistory.slice(index + 1, 999)))}
        show={true}
        bg={jsonMessage.status === "warning" ? "warning" : "info"}
        // className="d-inline-block m-1"
        delay={jsonMessage.delay || 5000}
        autohide
    >
        <Toast.Header>
            <strong className="me-auto">Notification - {jsonMessage.category}</strong>
        </Toast.Header>
        <Toast.Body className="text-black">{jsonMessage.message}</Toast.Body>
    </Toast>
    }
  )
  return (
    <div className="main">
      <div className="d-lg-none nav-button">
        <Button variant="primary" type="submit" onClick={handleShowNav}>Nav</Button>
      </div>

      {/* <div className="navdiv"> */}
      {/* </div> */}
      <div className="main-body">
        <ToastContainer position="top-end">
            {toasts}
        </ToastContainer>
        <SideNavbar logged={props.logged} showNav={showNav} setShowNav={setShowNav} notifs={data.notifs}/>
        <div className="router">
          {/* <Router> */}
            <div className="router-body">
              <Routes>
                <Route path="/login" element={<Login logged={props.logged}/>}/>
                <Route path="/admin" element={<Admin />}/>
                <Route path="/createkingdom" element={<CreateKingdom loading={loading} updateData={updateData} kingdomid={data.kingdomid} state={data.state}/>}/>
                <Route element={<ProtectedRoute logged={props.logged} session={props.session} kingdomid={data.kingdomid}/>}>
                  <Route path="/status" element={<StatusContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/news" element={<NewsContent data={data} updateData={updateData}/>}/>
                  <Route path="/galaxy" element={<Galaxy data={data} loading={loading} updateData={updateData} initialGalaxyId={data.galaxies_inverted[data.kingdomid.kd_id]}/>}/>
                  <Route path="/message" element={<Message data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/forums" element={<Forums data={data} loading={loading}/>}/>
                  <Route path="/scores" element={<Scores data={data}/>}/>
                  <Route path="/history" element={<History data={data} loading={loading}/>}/>
                  <Route path="/build" element={<Build data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/settle" element={<Settle data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/structures" element={<Structures data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/military" element={<MilitaryContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/projects" element={<ProjectsContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/missiles" element={<Missiles data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/conquer" element={<ConquerContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/attack" element={<Attack data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/spy" element={<Spy data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/shareintel" element={<ShareIntel data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/launchmissiles" element={<LaunchMissiles data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/Schedule" element={<Schedule data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/primitives" element={<Primitives data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/galaxypolitics" element={<GalaxyPolitics data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/empirepolitics" element={<EmpirePolitics data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/universepolitics" element={<UniversePolitics data={data} loading={loading} updateData={updateData}/>}/>
                </Route>
                <Route path="/help" element={<Help/>}/>
                <Route path="/signup" element={<SignUp logged={props.logged}/>}/>
                <Route path="/forgot" element={<ForgotAccount/>}/>
                <Route path="/resetpassword" element={<ResetPassword/>}/>
                <Route path="/verifyemail" element={<VerifyEmail/>}/>
                <Route path="/" element={<Landing logged={props.logged}/>}/>
              </Routes>
            </div>
          {/* </Router> */}
        </div>
      </div>
    </div>
  )
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

function Home(props) {
  return (
    <div className="router-contents">
      <h2>Home</h2>
      <Login logged={props.logged}/>
    </div>
  )
}

function Login(props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('');
  const navigate = useNavigate();

  const onSubmitClick = (e)=>{
    setMessage("");
    e.preventDefault()
    let opts = {
      'username': username,
      'password': password
    }
    fetch('api/login', {
      method: 'post',

      body: JSON.stringify(opts)
    }).then(r => r.json())
      .then(session => {
        if (session.accessToken){
          login(session);
          navigate('/status');
        }
        else {
          setMessage("Invalid username/password")
        }
      })
  }

  const handleUsernameChange = (e) => {
    setUsername(e.target.value)
  }

  const handlePasswordChange = (e) => {
    setPassword(e.target.value)
  }

  return (
    <div>
      <h2>Login</h2>
      {!props.logged? <form action="#">
        <div>
          <input type="text" 
            placeholder="Username" 
            onChange={handleUsernameChange}
            value={username} 
          />
        </div>
        <div>
          <input
            type="password"
            placeholder="Password"
            onChange={handlePasswordChange}
            value={password}
            autoComplete="current-password"
          />
        </div>
        <button onClick={onSubmitClick} type="submit">
          Login
        </button>
        {
          message != ""
          ? <h2>{message}</h2>
          : null
        }
        <div><a href="/forgot">Forgot your password or username?</a></div>
      </form>
      : <button onClick={() => logout()}>Logout</button>}
    </div>
  )
}

function Finalize() {

  const [searchParams, setSearchParams] = useSearchParams();
  const [message, setMessage] = useState('');

  useEffect(() => {
    console.log(searchParams);
    fetch('api/finalize', {
      method: 'get',
      headers: {'Authorization': 'Bearer ' + searchParams.get('token')}
    }).then(r => r.json()).then(r => {
      console.log(r);
      setMessage(r.access_token);
      console.log(message);
    });
  }, [])
  return (
    <h2>{message}</h2>
  )
}

export {App, initGlobalData};