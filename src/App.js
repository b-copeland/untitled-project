import React, { useEffect, useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Link,
  Outlet,
  useSearchParams
} from "react-router-dom";
import {login, authFetch, useAuth, logout} from "./auth";
import BasicExample from "./components/navbar";
import "./App.css"


const PrivateRoute = (rest) => {
  const [logged] = useAuth();

  return logged ? <Outlet /> : <Navigate to="/login" />;
}


export default function App() {
  return (
    <div className="main">
      <div className="navdiv">
        <BasicExample />
      </div>
      <div className="main-body">
        <Header />
        <div className="router">
          <Router>
            <div className="router-body">
              {/* A <Switch> looks through its children <Route>s and
                  renders the first one that matches the current URL. */}
              <Routes>
                <Route path="/login" element={<Login />}/>
                <Route path="/secret" element={<PrivateRoute/>}>
                  <Route path="/secret" element={<Secret/>}/>
                </Route>
                <Route path="/finalize" element={<Finalize />}/>
                <Route path="/" element={<Home />}/>
              </Routes>
            </div>
          </Router>
        </div>
      </div>
    </div>
  );
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
      date: new Date(this.state.serverstart.getTime() + (Date.now() - this.state.start))
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
  // const kd_info = authFetch("api/kingdom").then(r => r.json());
  
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
          <span>Power: {kdInfo.power}</span>
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
      {/* <Header /> */}
      <h2>Home</h2>
    </div>
  )
}

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const [logged] = useAuth();

  const onSubmitClick = (e)=>{
    e.preventDefault()
    console.log("You pressed login")
    let opts = {
      'username': username,
      'password': password
    }
    console.log(opts)
    fetch('api/login', {
      method: 'post',
      body: JSON.stringify(opts)
    }).then(r => r.json())
      .then(session => {
        if (session.accessToken){
          login(session)
          console.log(session)          
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

function Secret() {
  const [message, setMessage] = useState('')

  useEffect(() => {
    authFetch("api/protected").then(response => {
      if (response.status === 401){
        setMessage("Sorry you aren't authorized!")
        return null
      }
      return response.json()
    }).then(response => {
      if (response && response.message){
        setMessage(response.message)
      }
    })
  }, [])
  return (
    <h2>Secret: {message}</h2>
  )
}