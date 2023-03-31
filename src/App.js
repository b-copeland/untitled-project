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
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "./auth";
import BasicExample from "./components/navbar";
import 'bootstrap/dist/css/bootstrap.css';
import "./App.css";
import Admin from "./pages/admin.js";
import CreateKingdom from "./pages/createkingdom.js";
import StatusContent from "./pages/home/status.js";
import NewsContent from "./pages/home/news.js";
import Galaxy from "./pages/galaxy.js";
import Forums from "./pages/home/forums.js";
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
import Primitives from "./pages/conquer/primitives.js";
import GalaxyPolitics from "./pages/politics/galaxypolitics.js";
import EmpirePolitics from "./pages/politics/empirepolitics.js";
import UniversePolitics from "./pages/politics/universepolitics.js";


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

const initGlobalData = {
  'kingdomid': {},
  'kingdom': {},
  'state': {},
  'shields': {},
  'kingdoms': {},
  'galaxies': {},
  'galaxies_inverted': {},
  'empires': {},
  'empires_inverted': {},
  'news': [],
  'settle': {},
  'structures': {},
  'mobis': {},
  'missiles': {},
  'engineers': {},
  'projects': {},
  'revealed': {},
  'shared': {},
  'pinned': [],
  'galaxypolitics': {},
  'universepolitics': {},
  'attackhistory': [],
  'spyhistory': [],
  'missilehistory': [],
  'galaxynews': [],
  'empirenews': [],
  'universenews': [],
}
const initLoadingData = {
  'kingdomid': true,
  'kingdom': true,
  'state': true,
  'shields': true,
  'kingdoms': true,
  'galaxies': true,
  'galaxies_inverted': true,
  'empires': true,
  'empires_inverted': true,
  'news': true,
  'galaxynews': true,
  'empirenews': true,
  'universenews': true,
  'settle': true,
  'structures': true,
  'mobis': true,
  'missiles': true,
  'engineers': true,
  'projects': true,
  'revealed': true,
  'shared': true,
  'pinned': true,
  'galaxypolitics': true,
  'universepolitics': true,
  'attackhistory': true,
  'spyhistory': true,
  'missilehistory': true,
}
const endpoints = {
  'kingdomid': 'api/kingdomid',
  'kingdom': 'api/kingdom',
  'state': 'api/state',
  'shields': 'api/shields',
  'kingdoms': 'api/kingdoms',
  'galaxies': 'api/galaxies',
  'galaxies_inverted': 'api/galaxies_inverted',
  'empires': 'api/empires',
  'empires_inverted': 'api/empires_inverted',
  'news': 'api/news',
  'galaxynews': 'api/galaxynews',
  'empirenews': 'api/empirenews',
  'universenews': 'api/universenews',
  'settle': 'api/settle',
  'structures': 'api/structures',
  'mobis': 'api/mobis',
  'missiles': 'api/missiles',
  'engineers': 'api/engineers',
  'projects': 'api/projects',
  'revealed': 'api/revealed',
  'shared': 'api/shared',
  'pinned': 'api/pinned',
  'galaxypolitics': 'api/galaxypolitics',
  'universepolitics': 'api/universepolitics',
  'attackhistory': 'api/attackhistory',
  'spyhistory': 'api/spyhistory',
  'missilehistory': 'api/missilehistory',
}

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
  const [data, setData] = useState(initGlobalData);
  const [loading, setLoading] = useState(initLoadingData);
  const [initLoadComplete, setInitLoadComplete] = useState(false);
  const [lastResolves, setLastResolves] = useState({});
  // console.log(data);
  // console.log(loading);

  const updateData = async (keys, depFuncs=[]) => {
    var newValues = JSON.parse(JSON.stringify(data));
    var newLoading = {...loading};
    var loadKeys = keys;
    if (keys.includes("all")) {
      loadKeys = Object.keys(initGlobalData);
      console.log(loadKeys);
    }
    for (const key of loadKeys) {
      newLoading[key] = true;
    }
    // console.log(JSON.parse(JSON.stringify(newValues)));
    // console.log(newLoading);
    setLoading(newLoading);

    for (const depFunc of depFuncs) {
      await depFunc();
    }

    const fetchData = async () => {
      for (const key of loadKeys) {
        await authFetch(endpoints[key], {keepalive: true}).then(
          r => r.json()
        ).then(r => (newValues[key] = r)).catch(
          err => {
            console.log('Failed to fetch ' + key);
            console.log(err);
          }
        );
        newLoading[key] = false;
        setData(JSON.parse(JSON.stringify(newValues)));
        setLoading(newLoading);
      }
    }
    await fetchData();
    
    // console.log(JSON.parse(JSON.stringify(newValues)));
    // console.log(JSON.parse(JSON.stringify(newLoading)));
  };

  const resolveKeysMap = {
    "generals": ["mobis"],
    "spy_attempt": [],
    "settles": ["settle", "structures"],
    "mobis": ["mobis"],
    "missiles": ["missiles"],
    "engineers": ["engineers"],
    "structures": ["structures"],
    "revealed": ["revealed"],
    "shared": ["shared"],
  }
  const refreshData = async () => {
    // console.log('Updating Data');
    // console.log(data);
    // console.log(lastResolves);
    if (initLoadComplete) {
      await updateData(["kingdom"]);
      if (Object.keys(lastResolves).length > 0) {
        const newResolves = Object.keys(lastResolves).filter(key => lastResolves[key] != data.kingdom.next_resolve[key]);
        // console.log(newResolves);
        var keysToUpdate = [];
        for (const resolve of newResolves) {
          keysToUpdate.push(...resolveKeysMap[resolve])
        }
        // console.log(keysToUpdate);
        updateData(keysToUpdate);
        setLastResolves(data.kingdom["next_resolve"]);
      }
    }
  }

  useEffect(() => {
    if (props.logged) {
      const keys = Object.keys(initGlobalData);
      const fetchData = async () => {
        await updateData(keys);
      }
      fetchData();
      setInitLoadComplete(true);

      // const interval = setInterval(() => {
      //   refreshData()
      // }, 10000);

      // return () => clearInterval(interval);
    }
  }, [props.logged])

  useInterval(() => {
    if (initLoadComplete) {
      if (data.kingdomid.created !== false) {
        refreshData()
      }
    }
  }, 10000)

  // console.log(data);
  // console.log(lastResolves);
  if (Object.keys(lastResolves || {}).length == 0 && data.kingdom.hasOwnProperty("next_resolve")) {
    setLastResolves(data.kingdom.next_resolve);
  }
  return (
    <div className="main">
      <div className="navdiv">
        <BasicExample />
      </div>
      <div className="main-body">
        <Header data={data}/>
        <div className="router">
          {/* <Router> */}
            <div className="router-body">
              <Routes>
                <Route path="/login" element={<Login logged={props.logged}/>}/>
                <Route path="/admin" element={<Admin />}/>
                <Route path="/createkingdom" element={<CreateKingdom loading={loading} updateData={updateData} kingdomid={data.kingdomid} state={data.state}/>}/>
                <Route element={<ProtectedRoute logged={props.logged} session={props.session} kingdomid={data.kingdomid}/>}>
                  <Route path="/status" element={<StatusContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/news" element={<NewsContent data={data}/>}/>
                  <Route path="/galaxy" element={<Galaxy data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/forums" element={<Forums/>}/>
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
                  <Route path="/primitives" element={<Primitives data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/galaxypolitics" element={<GalaxyPolitics data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/empirepolitics" element={<EmpirePolitics data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/universepolitics" element={<UniversePolitics data={data} loading={loading} updateData={updateData}/>}/>
                </Route>
                <Route path="/finalize" element={<Finalize />}/>
                <Route path="/" element={<Home logged={props.logged}/>}/>
              </Routes>
            </div>
          {/* </Router> */}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [logged, session] = useAuth();

  if (session === null) {
    if (!!JSON.parse(localStorage.getItem("DOMNUS_GAME_TOKEN"))) {
      return null;
    }
  }
  return <Content logged={logged} session={session}/>;
}

class Clock extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      date: new Date(),
    };
  }

  async componentDidMount() {
    const serverstart = await authFetch('/api/time').then(r => r.json());
    this.timerID = setInterval(
      () => this.tick(),
      this.props.interval
    );
    this.setState({
      start: Date.now(),
      serverstart: new Date(serverstart),
    })
  }

  componentWillUnmount() {
    clearInterval(this.timerID);
  }

  tick() {
    this.setState({
      date: new Date(this.state.serverstart?.getTime() + (Date.now() - this.state.start))
    });
  }

  render() {
    return (
      <span>Time: {this.state.date.toLocaleTimeString()}</span>
    );
  }
}

function Header(props) {
  if (Object.keys(props.data?.kingdom).length === 0) {
    return null;
  }

  const kdInfo = props.data.kingdom;
  return (
    <div className="header-container">
      <div className="header-contents">
        <div className="header-item">
          <Clock interval={1000}/>
        </div>
        <div className="header-item">
          <span>Stars: {kdInfo.stars?.toLocaleString()}</span>
        </div>
        <div className="header-item">
          <span>Fuel: {Math.floor(kdInfo.fuel).toLocaleString()}</span>
        </div>
        <div className="header-item">
          <span>Pop: {Math.floor(kdInfo.population).toLocaleString()}</span>
        </div>
        <div className="header-item">
          <span>Money: {Math.floor(kdInfo.money).toLocaleString()}</span>
        </div>
        <div className="header-item">
          <span>Score: {Math.floor(kdInfo.score).toLocaleString()}</span>
        </div>
        <div className="header-item">
          <span>Spy Attempts: {kdInfo.spy_attempts}</span>
        </div>
        <div className="header-item">
          <span>Generals: {kdInfo.generals_available}</span>
        </div>
      </div>
    </div>
  )
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
  const navigate = useNavigate();

  const onSubmitClick = (e)=>{
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
          console.log("Please type in correct username/password")
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
          />
        </div>
        <button onClick={onSubmitClick} type="submit">
          Login Now
        </button>
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