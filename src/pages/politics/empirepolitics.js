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
  const onSubmitLeaveClick = (e)=>{
      const updateFunc = () => authFetch('api/leaveempire', {
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
  const galaxyEmpireRequestRows = (props.data.galaxypolitics.empire_join_requests || []).map((empireId, iter) =>
    <tr key={"galaxy_empire_request_" + iter}>
      <td>{props.data.empires[empireId].name}</td>
      <td>
        {
          props.loading.galaxypolitics
          ? <Button className="empire-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="empire-button" variant="primary" type="submit" onClick={(e) => onSubmitCancelJoinClick(e, empireId)}>
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
          ? <Button className="empire-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="empire-button" variant="primary" type="submit" onClick={(e) => onSubmitAcceptInviteClick(e, empireId)}>
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
          ? <Button className="empire-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="empire-button" variant="primary" type="submit" onClick={(e) => onSubmitAcceptRequestClick(e, galaxyId)}>
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
          ? <Button className="empire-button" variant="primary" type="submit" disabled>
              Loading...
          </Button>
          : <Button className="empire-button" variant="primary" type="submit" onClick={(e) => onSubmitCancelInviteClick(e, galaxyId)}>
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
                  props.loading.empires
                  ? <Button className="empire-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="empire-button" variant="primary" type="submit" onClick={onSubmitNameClick}>
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
                  ? <Button className="empire-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="empire-button" variant="primary" type="submit" onClick={onSubmitJoinClick}>
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
                  ? <Button className="empire-button" variant="primary" type="submit" disabled>
                      Loading...
                  </Button>
                  : <Button className="empire-button" variant="primary" type="submit" onClick={onSubmitInviteClick}>
                      Invite
                  </Button>
                }
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
              <div className="leave-empire">
                  <h3>Danger Zone</h3>
                  {
                    props.loading.empirepolitics
                    ? <Button className="empire-button" variant="warning" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="empire-button" variant="warning" type="submit" onClick={onSubmitLeaveClick}>
                        Leave Empire
                    </Button>
                  }
              </div>
          </div>
      }
      </>
  )
}

function Status(props) {
    const [selectedEmpire, setSelectedEmpire] = useState(undefined);
    const [results, setResults] = useState([]);
    const [selectedEmpireRequest, setSelectedEmpireRequest] = useState(undefined);
    const [selectedEmpireOffer, setSelectedEmpireOffer] = useState(undefined);
    const [selectedTypeRequest, setSelectedTypeRequest] = useState(undefined);
    const [selectedValueRequest, setSelectedValueRequest] = useState(undefined);
    const [selectedTypeOffer, setSelectedTypeOffer] = useState(undefined);
    const [selectedValueOffer, setSelectedValueOffer] = useState(undefined);

    const handleChangeEmpire = (selectedOption) => {
      setSelectedEmpire(selectedOption.value);
    };
    const handleChangeEmpireRequest = (selectedOption) => {
        setSelectedEmpireRequest(selectedOption.value);
    };
    const handleChangeEmpireOffer = (selectedOption) => {
        setSelectedEmpireOffer(selectedOption.value);
    };
    const handleChangeTypeRequest = (selectedOption) => {
        setSelectedTypeRequest(selectedOption.value);
    };
    const handleChangeValueRequest = (selectedOption) => {
        setSelectedValueRequest(selectedOption.value);
    };
    const handleChangeTypeOffer = (selectedOption) => {
        setSelectedTypeOffer(selectedOption.value);
    };
    const handleChangeValueOffer = (selectedOption) => {
        setSelectedValueOffer(selectedOption.value);
    };
    const onSubmitDenounceClick = (e)=>{
        const updateFunc = () => authFetch('api/empire/' + selectedEmpire + '/denounce', {
            method: 'post',
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires'], [updateFunc])
    }
    const onSubmitDeclareClick = (e)=>{
        const updateFunc = () => authFetch('api/empire/' + selectedEmpire + '/declare', {
            method: 'post',
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires'], [updateFunc])
    }
    const onSubmitRequestSurrender = (e)=>{
        if (
            (selectedEmpireRequest === undefined)
            || (selectedTypeRequest === undefined)
            || (selectedValueRequest == undefined)
        ) {
            setResults(results.concat({
                "message": "Please fill out all surrender options"
            }))
            return
        }
        let opts = {
            "type": selectedTypeRequest,
            "value": selectedValueRequest,
        }
        const updateFunc = () => authFetch('api/empire/' + selectedEmpireRequest + '/surrenderrequest', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires', 'empirepolitics'], [updateFunc])
    }
    const onSubmitOfferSurrender = (e)=>{
        if (
            (selectedEmpireOffer === undefined)
            || (selectedTypeOffer === undefined)
            || (selectedValueOffer == undefined)
        ) {
            setResults(results.concat({
                "message": "Please fill out all surrender options"
            }))
            return
        }
        let opts = {
            "type": selectedTypeOffer,
            "value": selectedValueOffer,
        }
        const updateFunc = () => authFetch('api/empire/' + selectedEmpireOffer + '/surrenderoffer', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires', 'empirepolitics'], [updateFunc])
    }



    const onClickCancelOffer = (empire, type, value) => {
        let opts = {
            "type": type,
            "value": value,
        }
        const updateFunc = () => authFetch('api/empire/' + empire + '/cancelsurrenderoffer', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires', 'empirepolitics'], [updateFunc])
    };
    const onClickCancelRequest = (empire, type, value) => {
        let opts = {
            "type": type,
            "value": value,
        }
        const updateFunc = () => authFetch('api/empire/' + empire + '/cancelsurrenderrequest', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['empires', 'empirepolitics'], [updateFunc])
    };
    const onClickAcceptOffer = (empire, type, value) => {
        let opts = {
            "type": type,
            "value": value,
        }
        const updateFunc = () => authFetch('api/empire/' + empire + '/acceptsurrenderoffer', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['all'], [updateFunc])
    };
    const onClickAcceptRequest = (empire, type, value) => {
        let opts = {
            "type": type,
            "value": value,
        }
        const updateFunc = () => authFetch('api/empire/' + empire + '/acceptsurrenderrequest', {
            method: 'post',
            body: JSON.stringify(opts),
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['all'], [updateFunc])
    };



    const empireOptions = Object.keys(props.data.empires).map((empireId) => {
        return {"value": empireId, "label": props.data.empires[empireId].name}
    })
    const typeOptions = Object.keys(props.data.state.surrender_options || {}).map((type) => {
        return {"value": type, "label": type}
    })
    const requestValueOptions = ((props.data.state.surrender_options || {})[selectedTypeRequest] || []).map((value) => {
        return {"value": value, "label": value}
    })
    const offerValueOptions = ((props.data.state.surrender_options || {})[selectedTypeOffer] || []).map((value) => {
        return {"value": value, "label": value}
    })

    const empireMap = props.data.empires[(props.data.empires_inverted.empires_inverted || {})[props.data.kingdomid.kd_id]] || {};
    const empireSurrenderOptions = empireMap.war?.map(empireId =>{
        return {"value": empireId, "label": props.data.empires[empireId].name}
    })
    const empireWars = empireMap.war?.map(empireId =>
        <tr key={"empire_war_status_" + empireId}>
            <td>{props.data.empires[empireId].name}</td>
            <td>War</td>
            <td>N/A</td>
        </tr>    
    )
    const empirePeace = (Object.keys(empireMap.peace || {})).map(empireId =>
        <tr key={"empire_peace_status_" + empireId}>
            <td>{props.data.empires[empireId].name}</td>
            <td>Peace</td>
            <td>Time...</td>
        </tr>    
    )
    const empireAggression = (Object.keys(empireMap.aggression || {})).map(empireId =>
        <tr key={"empire_aggression_status_" + empireId}>
            <td>{props.data.empires[empireId].name}</td>
            <td>Aggression - {Math.floor(empireMap.aggression[empireId]).toLocaleString()}</td>
            <td>N/A</td>
        </tr>    
    )
    const empireDenounced = empireMap.denounced !== undefined ? <tr>
        <td>{props.data.empires[empireMap.denounced].name}</td>
        <td>Denounced</td>
        <td>{empireMap.denounced_expires}</td>
    </tr>
    : null
    const empireSurpriseWar = empireMap.surprise_war_penalty ? <tr>
        <td>All</td>
        <td>Surprise War Penalty</td>
        <td>{empireMap.surprise_war_penalty_expires}</td>
    </tr>
    : null
    const surrenderOffersReceived = (props.data.empirepolitics.surrender_offers_received || []).map(offer =>
        <tr key={"surrender_offers_received_" + offer.empire}>
            <td>{props.data.empires[offer.empire].name}</td>
            <td>{offer.type}</td>
            <td>{offer.value}</td>
            <td>
                {
                    props.loading.empirepolitics
                    ? <Button className="cancel-schedule-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="cancel-schedule" variant="primary" type="submit" onClick={() => onClickAcceptOffer(offer.empire, offer.type, offer.value)}>
                        Accept
                    </Button>
                }
            </td>
        </tr>
    )
    const surrenderOffersSent = (props.data.empirepolitics.surrender_offers_sent || []).map(offer =>
        <tr key={"surrender_offers_sent_" + offer.empire}>
            <td>{props.data.empires[offer.empire].name}</td>
            <td>{offer.type}</td>
            <td>{offer.value}</td>
            <td>
                {
                    props.loading.empirepolitics
                    ? <Button className="cancel-schedule-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="cancel-schedule" variant="primary" type="submit" onClick={() => onClickCancelOffer(offer.empire, offer.type, offer.value)}>
                        Cancel
                    </Button>
                }
            </td>
        </tr>
    )
    const surrenderRequestsReceived = (props.data.empirepolitics.surrender_requests_received || []).map(offer =>
        <tr key={"surrender_requests_received_" + offer.empire}>
            <td>{props.data.empires[offer.empire].name}</td>
            <td>{offer.type}</td>
            <td>{offer.value}</td>
            <td>
                {
                    props.loading.empirepolitics
                    ? <Button className="cancel-schedule-button" variant="danger" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="cancel-schedule" variant="danger" type="submit" onClick={() => onClickAcceptRequest(offer.empire, offer.type, offer.value)}>
                        Accept
                    </Button>
                }
            </td>
        </tr>
    )
    const surrenderRequestsSent = (props.data.empirepolitics.surrender_requests_sent || []).map(offer =>
        <tr key={"surrender_requests_sent_" + offer.empire}>
            <td>{props.data.empires[offer.empire].name}</td>
            <td>{offer.type}</td>
            <td>{offer.value}</td>
            <td>
                {
                    props.loading.empirepolitics
                    ? <Button className="cancel-schedule-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="cancel-schedule" variant="primary" type="submit" onClick={() => onClickCancelRequest(offer.empire, offer.type, offer.value)}>
                        Cancel
                    </Button>
                }
            </td>
        </tr>
    )
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
    return (
        <div className="empire-status">
            <ToastContainer position="bottom-end">
                {toasts}
            </ToastContainer>
            <div className="declare-war">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select an Empire
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
                <div className="empire-status-buttons">
                    {
                        props.loading.empires
                        ? <Button className="empire-button" variant="Primary" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="empire-button" variant="primary" type="submit" onClick={onSubmitDenounceClick}>
                            Denounce
                        </Button>
                    }
                    {
                        props.loading.empires
                        ? <Button className="empire-button" variant="warning" type="submit" disabled>
                            Loading...
                        </Button>
                        : <Button className="empire-button" variant="warning" type="submit" onClick={onSubmitDeclareClick}>
                            Declare War
                        </Button>
                    }
                </div>
            </div>
            <div className="empire-statuses">
                <h3>Empire Statuses</h3>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Status</th>
                            <th>Time Remaining</th>
                        </tr>
                    </thead>
                    <tbody>
                        {empireWars}
                        {empirePeace}
                        {empireDenounced}
                        {empireAggression}
                        {empireSurpriseWar}
                    </tbody>
                </Table>
            </div>
            <div className="empire-surrender-requests">
                <h3>Opponent's Surrender</h3>
                <label id="aria-label" htmlFor="aria-example-input">
                    Request Opponent's Surrender
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={empireSurrenderOptions}
                    onChange={handleChangeEmpireRequest}
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
                <label id="aria-label" htmlFor="aria-example-input">
                    Type of Surrender
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={typeOptions}
                    onChange={handleChangeTypeRequest}
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
                <label id="aria-label" htmlFor="aria-example-input">
                    Value
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={requestValueOptions}
                    onChange={handleChangeValueRequest}
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
                    ? <Button className="surrender-request-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="surrender-request-schedule" variant="primary" type="submit" onClick={onSubmitRequestSurrender}>
                        Request
                    </Button>
                }
                <h5>Surrender Requests Sent</h5>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Type</th>
                            <th>Value</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody>
                        {surrenderRequestsSent}
                    </tbody>
                </Table>
                <h5>Surrender Offers Received</h5>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Type</th>
                            <th>Value</th>
                            <th>Accept Surrender</th>
                        </tr>
                    </thead>
                    <tbody>
                        {surrenderOffersReceived}
                    </tbody>
                </Table>
            </div>
            <div className="empire-surrender-requests">
                <h3>Your Surrender</h3>
                <label id="aria-label" htmlFor="aria-example-input">
                    Offer Your Surrender
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={empireSurrenderOptions}
                    onChange={handleChangeEmpireOffer}
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
                <label id="aria-label" htmlFor="aria-example-input">
                    Type of Surrender
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={typeOptions}
                    onChange={handleChangeTypeOffer}
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
                <label id="aria-label" htmlFor="aria-example-input">
                    Value
                </label>
                <Select
                    id="select-empire"
                    className="join-empire-select"
                    options={offerValueOptions}
                    onChange={handleChangeValueOffer}
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
                    ? <Button className="surrender-offer-button" variant="danger" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="surrender-offer-schedule" variant="danger" type="submit" onClick={onSubmitOfferSurrender}>
                        Offer
                    </Button>
                }
                <h5>Surrender Offers Sent</h5>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Type</th>
                            <th>Value</th>
                            <th>Cancel</th>
                        </tr>
                    </thead>
                    <tbody>
                        {surrenderOffersSent}
                    </tbody>
                </Table>
                <h5>Surrender Requests Received</h5>
                <Table striped bordered hover className="galaxy-leader-table">
                    <thead>
                        <tr>
                            <th>Empire</th>
                            <th>Type</th>
                            <th>Value</th>
                            <th>Surrender</th>
                        </tr>
                    </thead>
                    <tbody>
                        {surrenderRequestsReceived}
                    </tbody>
                </Table>
            </div>
        </div>
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