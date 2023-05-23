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
import {adminAuth} from "../auth";
import Button from 'react-bootstrap/Button';
import Form from 'react-bootstrap/Form';
import Modal from 'react-bootstrap/Modal';

function Admin(props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [gameStart, setGameStart] = useState('');
  const [gameEnd, setGameEnd] = useState('');
  const [electionStart, setElectionStart] = useState('');
  const [numGalaxies, setNumGalaxies] = useState('');
  const [maxGalaxySize, setMaxGalaxySize] = useState('');
  const [avgSizeNewGalaxy, setAvgSizeNewGalaxy] = useState('');
  const [createMessage, setCreateMessage] = useState('');
  const [updateMessage, setUpdateMessage] = useState('');
  const [resetMessage, setResetMessage] = useState('');
  const [adminLogged, adminSession] = adminAuth.useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [showUpdate, setShowUpdate] = useState(false);
  const navigate = useNavigate();

  const onSubmitClick = (e)=>{
    e.preventDefault()
    let opts = {
      'username': username,
      'password': password
    }
    fetch('api/adminlogin', {
      method: 'post',
      body: JSON.stringify(opts)
    }).then(r => r.json())
      .then(session => {
        if (session.accessToken){
          adminAuth.login(session);
        //   navigate('/status');
        }
        else {
          console.log("Please type in correct username/password")
        }
      })
  }

  const onSubmitReset = (e) => {
    adminAuth.authFetch('api/resetstate', {
        method: 'POST',
    }).then(r => r.json()).then(r => setResetMessage(r))
  }

  const onSubmitUpdate = (e) => {
    let opts = {
        "game_start": gameStart,
        "game_end": gameEnd,
        "election_start": electionStart,
        "election_end": "",
        "active_policies": [],
        "next_history": gameStart,
    }
    adminAuth.authFetch('api/updatestate', {
        method: 'POST',
        body: JSON.stringify(opts),
    }).then(r => r.json()).then(r => setUpdateMessage(r))
  }

  const onSubmitCreate = (e) => {
    let opts = {
        "num_galaxies": numGalaxies,
        "max_galaxy_size": maxGalaxySize,
        "avg_size_new_galaxy": avgSizeNewGalaxy
    }
    adminAuth.authFetch('api/createstate', {
        method: 'POST',
        body: JSON.stringify(opts),
    }).then(r => r.json()).then(r => setCreateMessage(r))
  }


  const handleUsernameChange = (e) => {
    setUsername(e.target.value)
  }

  const handlePasswordChange = (e) => {
    setPassword(e.target.value)
  }
  const handleGameStartChange = (e) => {
    setGameStart(e.target.value)
  }
  const handleGameEndChange = (e) => {
    setGameEnd(e.target.value)
  }
  const handleElectionStartChange = (e) => {
    setElectionStart(e.target.value)
  }
  const handleNumGalaxiesChange = (e) => {
    setNumGalaxies(e.target.value)
  }
  const handleMaxGalaxySizeChange = (e) => {
    setMaxGalaxySize(e.target.value)
  }
  const handleAvgSizeNewGalaxyChange = (e) => {
    setAvgSizeNewGalaxy(e.target.value)
  }

  return (
    <div>
        <Modal
            show={showReset}
            onHide={() => setShowReset(false)}
            animation={false}
            dialogClassName="reset-modal"
        >
            <Modal.Header closeButton>
                <Modal.Title>Reset</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <div>
                    <span>Confirm Reset?</span>
                    <Button onClick={onSubmitReset}>Reset State</Button>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={() => setShowReset(false)}>
                Close
                </Button>
            </Modal.Footer>
        </Modal>
        <Modal
            show={showUpdate}
            onHide={() => setShowUpdate(false)}
            animation={false}
            dialogClassName="update-modal"
        >
            <Modal.Header closeButton>
                <Modal.Title>Update Game State</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <div>
                    <span>Confirm Update?</span>
                    <Button onClick={onSubmitUpdate}>Update State</Button>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={() => setShowUpdate(false)}>
                Close
                </Button>
            </Modal.Footer>
        </Modal>
        <Modal
            show={showCreate}
            onHide={() => setShowCreate(false)}
            animation={false}
            dialogClassName="update-modal"
        >
            <Modal.Header closeButton>
                <Modal.Title>Create Game State</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <div>
                    <span>Confirm Create?</span>
                    <Button onClick={onSubmitCreate}>Create State</Button>
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={() => setShowCreate(false)}>
                Close
                </Button>
            </Modal.Footer>
        </Modal>
      <h2>Admin</h2>
      {
        !adminLogged
        ? <form action="#">
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
      : <div>
            <h3>Game Start</h3>
            <Form.Control 
                className="game-start-form"
                id="game-start-input"
                onChange={handleGameStartChange}
                value={gameStart || ""} 
                placeholder=""
            />
            <h3>Game End</h3>
            <Form.Control 
                className="game-end-form"
                id="game-end-input"
                onChange={handleGameEndChange}
                value={gameEnd || ""} 
                placeholder=""
            />
            <h3>Election Start</h3>
            <Form.Control 
                className="election-start-form"
                id="election-start-input"
                onChange={handleElectionStartChange}
                value={electionStart || ""} 
                placeholder=""
            />
            <Button onClick={() => {setShowUpdate(true)}}>Update Game State</Button>
            <h2>{updateMessage}</h2>
            <br />
            <h3>Starting Num Galaxies</h3>
            <Form.Control 
                className="num-galaxies-form"
                id="num-galaxies-input"
                onChange={handleNumGalaxiesChange}
                value={numGalaxies || ""} 
                placeholder=""
            />
            <h3>Max Galaxy Size</h3>
            <Form.Control 
                className="max-galaxy-size-form"
                id="max-galaxy-size-input"
                onChange={handleMaxGalaxySizeChange}
                value={maxGalaxySize || ""} 
                placeholder=""
            />
            <h3>Average Size for New Galaxy</h3>
            <Form.Control 
                className="avg-size-new-galaxy-form"
                id="avg-size-new-galaxy-input"
                onChange={handleAvgSizeNewGalaxyChange}
                value={avgSizeNewGalaxy || ""} 
                placeholder=""
            />
            <Button onClick={() => {setShowCreate(true)}}>Create State</Button>
            <h2>{createMessage}</h2>
            <br />
            <br />
            <Button onClick={() => {setShowReset(true)}}>Reset State</Button>
            <h2>{resetMessage}</h2>
            <br />
            <Button onClick={() => adminAuth.logout()}>Logout</Button>
        </div>
    }
    </div>
  )
}

export default Admin;