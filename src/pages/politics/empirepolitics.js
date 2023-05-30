import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer'
import "./empirepolitics.css";
import Select from 'react-select';
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";

function EmpirePolitics(props) {
    const [key, setKey] = useState('join');

    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="join"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="join" title="Join">
          <Join
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}
            />
        </Tab>
        <Tab eventKey="status" title="Status">
          <Status
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
        <Tab eventKey="politics" title="Politics">
          <Politics
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
        <Tab eventKey="targets" title="Targets">
          <Targets
            loading={props.loading}
            updateData={props.updateData}
            data={props.data}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"empirepolitics"}/>
    </>
    );
}

function Join(props) {
  const [selectedEmpire, setSelectedEmpire] = useState(undefined);
  const [selectedGalaxy, setSelectedGalaxy] = useState(undefined);
  const [results, setResults] = useState([]);
  const [empireName, setEmpireName] = useState();

  const handleChangeEmpire = (selectedOption) => {
    setSelectedEmpire(selectedOption.value);
  };
  const handleChangeGalaxy = (selectedOption) => {
    setSelectedGalaxy(selectedOption.value);
  };
  const handleNameInput = (e) => {
    setEmpireName(e.target.value);
  }

  const onSubmitNameClick = (e)=>{
      if (empireName != "") {
          let opts = {
              'empireName': empireName,
          };
          const updateFunc = () => authFetch('api/empire', {
              method: 'post',
              body: JSON.stringify(opts)
          }).then(r => r.json()).then(r => setResults(results.concat(r)))
          props.updateData(['empires', 'empires_inverted'], [updateFunc])
      }
  }
  const onSubmitJoinClick = (e)=>{
      const updateFunc = () => authFetch('api/empire/' + selectedEmpire + '/join', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['galaxypolitics'], [updateFunc])
  }
  const onSubmitCancelJoinClick = (e, empire)=>{
      const updateFunc = () => authFetch('api/empire/' + empire + '/canceljoin', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['galaxypolitics'], [updateFunc])
  }
  const onSubmitAcceptInviteClick = (e, empire)=>{
      const updateFunc = () => authFetch('api/empire/' + empire + '/acceptinvite', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['galaxypolitics', 'empires', 'empires_inverted'], [updateFunc])
  }
  const onSubmitInviteClick = (e)=>{
      const updateFunc = () => authFetch('api/galaxy/' + selectedGalaxy + '/invite', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['empirepolitics'], [updateFunc])
  }
  const onSubmitCancelInviteClick = (e, galaxy)=>{
      const updateFunc = () => authFetch('api/galaxy/' + galaxy + '/cancelinvite', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['empirepolitics'], [updateFunc])
  }
  const onSubmitAcceptRequestClick = (e, galaxy)=>{
      const updateFunc = () => authFetch('api/galaxy/' + galaxy + '/accept', {
          method: 'post',
      }).then(r => r.json()).then(r => setResults(results.concat(r)))
      props.updateData(['empirepolitics', 'empires', 'empires_inverted'], [updateFunc])
  }
  const empireOptions = Object.keys(props.data.empires).map((empireId) => {
      return {"value": empireId, "label": props.data.empires[empireId].name}
  })
  const galaxyOptions = Object.keys(props.data.galaxies).filter(
    (galaxyId) => !Object.keys(props.data.empires_inverted.galaxy_empires || {}).includes(galaxyId)
  ).map((galaxyId) => {
      return {"value": galaxyId, "label": galaxyId}
  })
  const toasts = results.map((resultsItem, index) =>
      <Toast
          key={index}
          onClose={(e) => setResults(results.slice(0, index).concat(results.slice(index + 1, 999)))}
          show={true}
          bg={resultsItem.status === "success" ? "success" : "warning"}
      >
          <Toast.Header>
              <strong className="me-auto">Empire Results</strong>
          </Toast.Header>
          <Toast.Body  className="text-black">{resultsItem.message}</Toast.Body>
      </Toast>
  )
  console.log(props.data.empires_inverted);
  console.log(props.data.galaxypolitics);
  const galaxyEmpireRequestRows = (props.data.galaxypolitics.empire_join_requests || []).map((empireId, iter) =>
    <tr key={"galaxy_empire_request_" + iter}>
      <td>{props.data.empires[empireId].name}</td>
      <td>
        {
          props.loading.galaxypolitics
          ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="submit-name-button" variant="primary" type="submit" onClick={(e) => onSubmitCancelJoinClick(e, empireId)}>
              Cancel
          </Button>
        }
      </td>
    </tr>
  )
  const galaxyEmpireInvitationRows = (props.data.galaxypolitics.empire_invitations || []).map((empireId, iter) =>
    <tr key={"galaxy_empire_invitation_" + iter}>
      <td>{props.data.empires[empireId].name}</td>
      <td>
        {
          props.loading.galaxypolitics
          ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="submit-name-button" variant="primary" type="submit" onClick={(e) => onSubmitAcceptInviteClick(e, empireId)}>
              Accept
          </Button>
        }
      </td>
    </tr>
  )
  const empireGalaxyRequestRows = (props.data.empirepolitics.empire_join_requests || []).map((galaxyId, iter) =>
    <tr key={"empire_galaxy_request_" + iter}>
      <td>{galaxyId}</td>
      <td>
        {
          props.loading.empirepolitics
          ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="submit-name-button" variant="primary" type="submit" onClick={(e) => onSubmitAcceptRequestClick(e, galaxyId)}>
              Accept
          </Button>
        }
      </td>
    </tr>
  )
  const empireGalaxyInvitationRows = (props.data.empirepolitics.empire_invitations || []).map((galaxyId, iter) =>
    <tr key={"empire_galaxy_invitation_" + iter}>
      <td>{galaxyId}</td>
      <td>
        {
          props.loading.empirepolitics
          ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="submit-name-button" variant="primary" type="submit" onClick={(e) => onSubmitCancelInviteClick(e, galaxyId)}>
              Cancel
          </Button>
        }
      </td>
    </tr>
  )
  return (
      <>
      <ToastContainer position="bottom-end">
          {toasts}
      </ToastContainer>
      {
          (props.data.empires_inverted.empires_inverted || {})[props.data.kingdomid.kd_id] === undefined
          ? <div className="join-empire-page">
              <div className="create-empire">
                <h3>Create an Empire</h3>
                <InputGroup className="kd-name-group">
                    <InputGroup.Text id="kd-name-input-display">
                        Empire Name
                    </InputGroup.Text>
                    <Form.Control 
                        id="empire-name-input"
                        onChange={handleNameInput}
                        value={empireName || ""} 
                        placeholder=""
                        autoComplete="off"
                    />
                </InputGroup>
                {
                  props.loading.galaxypolitics
                  ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitNameClick}>
                      Create
                  </Button>
                }
              </div>
              <div className="join-empire">
                <label id="aria-label" htmlFor="aria-example-input">
                    Request to join an Empire
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={empireOptions}
                    onChange={handleChangeEmpire}
                    autoFocus={false}
                    styles={{
                        control: (baseStyles, state) => ({
                            ...baseStyles,
                            borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                            backgroundColor: 'var(--bs-body-bg)',
                        }),
                        placeholder: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-primary-text)',
                        }),
                        input: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                        option: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                            color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                        }),
                        menuList: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: 'var(--bs-secondary-bg)',
                            // borderColor: 'var(--bs-secondary-bg)',
                        }),
                        singleValue: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                    }}/>
                {
                  props.loading.galaxypolitics
                  ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitJoinClick}>
                      Request
                  </Button>
                }
              </div>
              <div className="empire-membership-table">
                <h3>Empire Invitations</h3>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Accept</th>
                        </tr>
                    </thead>
                    <tbody>
                        {galaxyEmpireInvitationRows}
                    </tbody>
                </Table>
              </div>
              <div className="empire-membership-table">
                <h3>Empire Join Requests</h3>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody>
                        {galaxyEmpireRequestRows}
                    </tbody>
                </Table>
              </div>
          </div>
          : <div className="join-empire-page">
              <div className="invite-empire">
                <label id="aria-label" htmlFor="aria-example-input">
                    Invite Galaxies
                </label>
                <Select
                    id="select-galaxy"
                    className="invite-galaxy-select"
                    options={galaxyOptions}
                    onChange={handleChangeGalaxy}
                    autoFocus={false}
                    styles={{
                        control: (baseStyles, state) => ({
                            ...baseStyles,
                            borderColor: state.isFocused ? 'var(--bs-body-color)' : 'var(--bs-primary-text)',
                            backgroundColor: 'var(--bs-body-bg)',
                        }),
                        placeholder: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-primary-text)',
                        }),
                        input: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                        option: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: state.isFocused ? 'var(--bs-primary-bg-subtle)' : 'var(--bs-secondary-bg-subtle)',
                            color: state.isFocused ? 'var(--bs-primary-text)' : 'var(--bs-secondary-text)',
                        }),
                        menuList: (baseStyles, state) => ({
                            ...baseStyles,
                            backgroundColor: 'var(--bs-secondary-bg)',
                            // borderColor: 'var(--bs-secondary-bg)',
                        }),
                        singleValue: (baseStyles, state) => ({
                            ...baseStyles,
                            color: 'var(--bs-secondary-text)',
                        }),
                    }}/>
                {
                  props.loading.empirepolitics
                  ? <Button className="submit-name-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="submit-name-button" variant="primary" type="submit" onClick={onSubmitInviteClick}>
                      Invite
                  </Button>
                }
              </div>
              <div className="leave-empire">
                  
              </div>
              <div className="empire-membership-table">
                <h3>Empire Join Requests</h3>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Galaxy</th>
                            <th>Accept</th>
                        </tr>
                    </thead>
                    <tbody>
                        {empireGalaxyRequestRows}
                    </tbody>
                </Table>
              </div>
              <div className="empire-membership-table">
                <h3>Empire Invitations</h3>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Galaxy</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody>
                        {empireGalaxyInvitationRows}
                    </tbody>
                </Table>
              </div>
          </div>
      }
      </>
  )
}

function Status(props) {
    return (
        <h3>Coming Soon</h3>
    )
}

function Politics(props) {
    return (
        <h3>Coming Soon</h3>
    )
}

function Targets(props) {
    return (
        <h3>Coming Soon</h3>
    )
}

export default EmpirePolitics;