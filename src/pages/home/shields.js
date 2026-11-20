import React, { useState } from "react";
import Form from 'react-bootstrap/Form';
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import { authFetch } from "../../auth";
import { displayPercent } from "../../format";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import "./status.css";
import "./shields.css";

/** The Shields & Spending page: the shields the kingdom pays fuel for, and how auto spending splits its money. */
function ShieldsAndSpending(props) {
    return (
        <>
            <Header data={props.data} />
            <div className="shields-spending">
                <section>
                    <h2>Shields</h2>
                    <Shields data={props.data} loading={props.loading} updateData={props.updateData} />
                </section>
                <section>
                    <Spending kingdom={props.data.kingdom} loading={props.loading} updateData={props.updateData} />
                </section>
            </div>
            <HelpButton scrollTarget={"shields"} />
        </>
    );
}

const initialShields = {
    "military": "",
    "spy": "",
    "spy_radar": "",
    "missiles": "",
}
function Shields(props) {
    const [shields, setShields] = useState(initialShields);
    const [results, setResults] = useState([]);
    
    const onClick = (e)=>{
        const opts = shields;
        const updateFunc = () => authFetch('api/shields', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
        // setShields(initialShields);
    }
    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setShields({
          ...shields,
          [name]: value,
        });
      };
    return (
        <div className="shields">
        <div className="shields-content">
            <ResultToasts title="Shields Results" results={results} setResults={setResults} />
            <Table className="shields-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Shield</th>
                        <th style={{textAlign: "right"}}>Current %</th>
                        <th style={{textAlign: "right"}}>Max %</th>
                        <th style={{textAlign: "right"}}>Current Power Cost</th>
                        <th style={{textAlign: "right"}}>Max Power Cost</th>
                        <td style={{textAlign: "right"}}>Input</td>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Military</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.kingdom.shields?.military || 0)}</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.shields.desc?.military?.max || 0)}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.kingdom.shields?.military * props.data.shields.desc?.military?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.shields.desc?.military?.max * props.data.shields.desc?.military?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3 shields-input-group">
                                <Form.Control
                                className="shields-assign-form"
                                id="military-input"
                                onChange={handleInputChange}
                                name="military"
                                value={shields.military || ""} 
                                placeholder="0"
                                autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Spy</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.kingdom.shields?.spy || 0)}</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.shields.desc?.spy?.max || 0)}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.kingdom.shields?.spy * props.data.shields.desc?.spy?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.shields.desc?.spy?.max * props.data.shields.desc?.spy?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3 shields-input-group">
                                <Form.Control
                                className="shields-assign-form"
                                id="spy-input"
                                onChange={handleInputChange}
                                name="spy"
                                value={shields.spy || ""} 
                                placeholder="0"
                                autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Spy Radar</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.kingdom.shields?.spy_radar || 0)}</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.shields.desc?.spy_radar?.max || 0)}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.kingdom.shields?.spy_radar * props.data.shields.desc?.spy_radar?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.shields.desc?.spy_radar?.max * props.data.shields.desc?.spy_radar?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3 shields-input-group">
                                <Form.Control
                                className="shields-assign-form"
                                id="spy-radar-input"
                                onChange={handleInputChange}
                                name="spy_radar"
                                value={shields.spy_radar || ""} 
                                placeholder="0"
                                autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Missiles</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.kingdom.shields?.missiles || 0)}</td>
                        <td style={{textAlign: "right"}}>{displayPercent(props.data.shields.desc?.missiles?.max || 0)}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.kingdom.shields?.missiles * props.data.shields.desc?.missiles?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{Math.floor(props.data.shields.desc?.missiles?.max * props.data.shields.desc?.missiles?.cost * props.data.kingdom.stars * 100 || 0).toLocaleString()}</td>
                        <td>
                            <InputGroup className="mb-3 shields-input-group">
                                <Form.Control
                                className="shields-assign-form"
                                id="missiles-input"
                                onChange={handleInputChange}
                                name="missiles"
                                value={shields.missiles || ""} 
                                placeholder="0"
                                autoComplete="off"
                                />
                                <InputGroup.Text id="basic-addon2">%</InputGroup.Text>
                            </InputGroup>
                        </td>
                    </tr>
                </tbody>
            </Table>
            {props.loading.kingdom
            ? <Button className="shields-button" variant="primary" type="submit" disabled>
                Loading...
            </Button>
            : <Button className="shields-button" variant="primary" type="submit" onClick={onClick}>
                Update
            </Button>
            }
        </div>
        </div>
    )
}

function Spending(props) {
    const [settleInput, setSettleInput] = useState('');
    const [structuresInput, setStructuresInput] = useState('');
    const [militaryInput, setMilitaryInput] = useState('');
    const [engineersInput, setEngineersInput] = useState('');
    const [enabled, setEnabled] = useState(props.kingdom.auto_spending_enabled)
    const [results, setResults] = useState([]);

    const spendingInfo = props.kingdom?.auto_spending;
    if (spendingInfo === undefined) {
        return null
    }

    const handleSettleInput = (e) => {
        setSettleInput(e.target.value)
    }
  
    const handleStructuresInput = (e) => {
        setStructuresInput(e.target.value)
    }

    const handleMilitaryInput = (e) => {
        setMilitaryInput(e.target.value)
    }
  
    const handleEngineersInput = (e) => {
        setEngineersInput(e.target.value)
    }
    const handleEnabledChange = (e) => {
        let opts = {
            'enabled': e.target.checked
        }
        const updateFunc = () => authFetch('api/spending', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setEnabled(e.target.checked)
    }

    const onSubmitClick = async (e)=>{
        let opts = {
            'settle': settleInput === '' ? undefined : settleInput,
            'structures': structuresInput === '' ? undefined : structuresInput,
            'military': militaryInput === '' ? undefined : militaryInput,
            'engineers': engineersInput === '' ? undefined : engineersInput,
        }
        const updateFunc = () => authFetch('api/spending', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setResults(results.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setSettleInput('');
        setStructuresInput('');
        setMilitaryInput('');
        setEngineersInput('');
    }
    return (
        <div className="spending">
            <ResultToasts title="Auto Spending Results" results={results} setResults={setResults} />
            <h2>Update Auto Spending:</h2>
            <Form>
                <Form.Check 
                    type="switch"
                    id="enable-auto-spending-switch"
                    label="Enable"
                    defaultChecked={enabled}
                    onChange={handleEnabledChange}
                    disabled={props.loading.kingdom}
                />
            </Form>
            <div className="col-center-full spending-inputs">
                <InputGroup className="mb-3">
                    <InputGroup.Text id="text-settle-percent" className="spending-title">
                        Settle (Current: {spendingInfo.settle * 100}%)
                    </InputGroup.Text>
                    <Form.Control 
                        id="settle-percent"
                        aria-describedby="basic-addon3" 
                        onChange={handleSettleInput}
                        value={settleInput} 
                        placeholder={spendingInfo.settle * 100}
                        autoComplete="off"
                    />
                    <InputGroup.Text id="text-engineers-percent" style={{width: '10%'}}>
                        %
                    </InputGroup.Text>
                </InputGroup>
                <InputGroup className="mb-3">
                    <InputGroup.Text id="text-structures-percent" className="spending-title">
                        Structures (Current: {spendingInfo.structures * 100}%)
                    </InputGroup.Text>
                    <Form.Control 
                        id="structures-percent"
                        aria-describedby="basic-addon3" 
                        onChange={handleStructuresInput}
                        value={structuresInput} 
                        placeholder={spendingInfo.structures * 100}
                        autoComplete="off"
                    />
                    <InputGroup.Text id="text-engineers-percent" style={{width: '10%'}}>
                        %
                    </InputGroup.Text>
                </InputGroup>
                <InputGroup className="mb-3">
                    <InputGroup.Text id="text-military-percent" className="spending-title">
                        Military (Current: {spendingInfo.military * 100}%)
                    </InputGroup.Text>
                    <Form.Control 
                        id="military-percent"
                        aria-describedby="basic-addon3" 
                        onChange={handleMilitaryInput}
                        value={militaryInput} 
                        placeholder={spendingInfo.military * 100}
                        autoComplete="off"
                    />
                    <InputGroup.Text id="text-engineers-percent" style={{width: '10%'}}>
                        %
                    </InputGroup.Text>
                </InputGroup>
                <InputGroup className="mb-3">
                    <InputGroup.Text id="text-engineers-percent" className="spending-title">
                        Engineers (Current: {spendingInfo.engineers * 100}%)
                    </InputGroup.Text>
                    <Form.Control 
                        id="engineers-percent"
                        aria-describedby="basic-addon3" 
                        onChange={handleEngineersInput}
                        value={engineersInput} 
                        placeholder={spendingInfo.engineers * 100}
                        autoComplete="off"
                    />
                    <InputGroup.Text id="text-engineers-percent" style={{width: '10%'}}>
                        %
                    </InputGroup.Text>
                </InputGroup>
                {props.loading.kingdom
                ? <Button className="spending-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="spending-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Submit
                </Button>
                }
            </div>
            <div className="text-box kingdom-card">
                <h4>Auto Spending Funding</h4>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Settle</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.funding?.settle || 0).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Structures</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.funding?.structures || 0).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Military</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.funding?.military || 0).toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Engineers</span>
                    <span className="text-box-item-value">{Math.floor(props.kingdom.funding?.engineers || 0).toLocaleString()}</span>
                </div>
            </div>
        </div>
    )
}

export default ShieldsAndSpending;
