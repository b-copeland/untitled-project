import React, { useEffect, useState } from "react";
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
import "./App.css"
import StatusContent from "./pages/home/status.js"
import NewsContent from "./pages/home/news.js"
import Galaxy from "./pages/galaxy.js"
import Forums from "./pages/home/forums.js"
import History from "./pages/home/history.js"
import Settle from "./pages/build/settle.js"
import Structures from "./pages/build/structures.js"
import MilitaryContent from "./pages/build/military.js"
import ProjectsContent from "./pages/build/projects.js"
import Missiles from "./pages/build/missiles.js"



// const ProtectedRoute = ({ logged, session, redirectPath = '/login', children }) => {
//   const navigate = useNavigate();
//   useEffect(() => {
//     if (!logged) {
//       navigate(redirectPath, {replace: true});
//     }
//   }, [logged])

//   if (session != null && session.hasOwnProperty("error")) {
//     logout();
//     return <Navigate to={redirectPath} replace />;
//   }

//   return children ? children : <Outlet />;
// };


const ProtectedRoute = ({ logged, session, redirectPath = '/login', children }) => {
  if (session != null && session.hasOwnProperty("error")) {
    logout();
    return <Navigate to={redirectPath} replace />;
  }
  if (!logged) {
    return <Navigate to={redirectPath} replace />;
  }

  return children ? children : <Outlet />;
};

const PrivateRoute = ({

}) => {
  const [logged, session] = useAuth();

  if (session === null) {
    return null;
  }

  return logged ? <Outlet /> : <Navigate to="/login" />;
}

const initGlobalData = {
  'kingdom': {},
  'kingdoms': {},
  'galaxies': {},
  'galaxies_inverted': {},
  'news': [],
  'galaxynews': [],
  'empirenews': [],
  'universenews': [],
  'settle': {},
  'structures': {},
  'mobis': {},
  'missiles': {},
  'engineers': {},
  'projects': {},
}
const initLoadingData = {
  'kingdom': true,
  'kingdoms': true,
  'galaxies': true,
  'galaxies_inverted': true,
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
}
const endpoints = {
  'kingdom': 'api/kingdom',
  'kingdoms': 'api/kingdoms',
  'galaxies': 'api/galaxies',
  'galaxies_inverted': 'api/galaxies_inverted',
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
}

function Content(props) {
  const [data, setData] = useState(initGlobalData);
  const [loading, setLoading] = useState(initLoadingData);

  const updateData = async (keys, depFuncs=[]) => {
    var newValues = JSON.parse(JSON.stringify(data));
    var newLoading = {...loading};
    for (const key of keys) {
      newLoading[key] = true;
    }
    console.log(JSON.parse(JSON.stringify(newValues)));
    console.log(newLoading);
    setLoading(newLoading);

    for (const depFunc of depFuncs) {
      await depFunc();
    }

    const fetchData = async () => {
      for (const key of keys) {
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
    
    console.log(JSON.parse(JSON.stringify(newValues)));
    console.log(JSON.parse(JSON.stringify(newLoading)));
  };

  useEffect(() => {
    const keys = Object.keys(initGlobalData);
    updateData(keys);
  }, [])
  if (props.session === null) {
    if (!!JSON.parse(localStorage.getItem("DOMNUS_GAME_TOKEN"))) {
      return null;
    }
  }
  return (
    <div className="main">
      <div className="navdiv">
        <BasicExample />
      </div>
      <div className="main-body">
        <Header />
        <div className="router">
          {/* <Router> */}
            <div className="router-body">
              <Routes>
                <Route path="/login" element={<Login />}/>
                <Route element={<ProtectedRoute logged={props.logged} session={props.session}/>}>
                  <Route path="/status" element={<StatusContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/news" element={<NewsContent data={data}/>}/>
                  <Route path="/galaxy" element={<Galaxy data={data}/>}/>
                  <Route path="/forums" element={<Forums/>}/>
                  <Route path="/history" element={<History/>}/>
                  <Route path="/settle" element={<Settle data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/structures" element={<Structures data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/military" element={<MilitaryContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/projects" element={<ProjectsContent data={data} loading={loading} updateData={updateData}/>}/>
                  <Route path="/missiles" element={<Missiles data={data} loading={loading} updateData={updateData}/>}/>
                </Route>
                <Route path="/finalize" element={<Finalize />}/>
                <Route path="/" element={<Home />}/>
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

  return <Content logged={logged} session={session}/>;
}

// export default function App() {
//   return (
//     <div className="main">
//       <div className="navdiv">
//         <BasicExample />
//       </div>
//       <div className="main-body">
//         <Header />
//         <div className="router">
//           {/* <Router> */}
//             <div className="router-body">
//               <Routes>
//                 <Route path="/login" element={<Login />}/>
//                 <Route path="/status" element={<PrivateRoute/>}>
//                   <Route path="/status" element={<StatusContent/>}/>
//                 </Route>
//                 <Route path="/news" element={<PrivateRoute/>}>
//                   <Route path="/news" element={<NewsContent/>}/>
//                 </Route>
//                 <Route path="/galaxy" element={<PrivateRoute/>}>
//                   <Route path="/galaxy" element={<Galaxy/>}/>
//                 </Route>
//                 <Route path="/forums" element={<PrivateRoute/>}>
//                   <Route path="/forums" element={<Forums/>}/>
//                 </Route>
//                 <Route path="/history" element={<PrivateRoute/>}>
//                   <Route path="/history" element={<History/>}/>
//                 </Route>
//                 <Route path="/settle" element={<PrivateRoute/>}>
//                   <Route path="/settle" element={<Settle/>}/>
//                 </Route>
//                 <Route path="/structures" element={<PrivateRoute/>}>
//                   <Route path="/structures" element={<Structures/>}/>
//                 </Route>
//                 <Route path="/military" element={<PrivateRoute/>}>
//                   <Route path="/military" element={<MilitaryContent/>}/>
//                 </Route>
//                 <Route path="/finalize" element={<Finalize />}/>
//                 <Route path="/" element={<Home />}/>
//               </Routes>
//             </div>
//           {/* </Router> */}
//         </div>
//       </div>
//     </div>
//   );
// }

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

function Header() {
  const [kdInfo, setKdInfo] = useState({});
  
  useEffect(() => {
    const fetchData = async () => {
      await authFetch("api/kingdom").then(r => r.json()).then(r => setKdInfo(r));
    }
    fetchData();
  }, [])

  return (
    <div className="header-container">
      <div className="header-contents">
        <div className="header-item">
          <Clock interval={1000}/>
        </div>
        <div className="header-item">
          <span>Stars: {kdInfo.stars}</span>
        </div>
        <div className="header-item">
          <span>Fuel: {kdInfo.fuel}</span>
        </div>
        <div className="header-item">
          <span>Pop: {kdInfo.population}</span>
        </div>
        <div className="header-item">
          <span>Money {kdInfo.money}</span>
        </div>
        <div className="header-item">
          <span>Score: {kdInfo.score}</span>
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

function Home() {
  return (
    <div className="router-contents">
      <h2>Home</h2>
      <Login />
    </div>
  )
}

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [logged] = useAuth();
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
      {!logged? <form action="#">
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