import React, { useState } from "react";
import Form from 'react-bootstrap/Form';
import { NumberControl } from "../../components/forms";
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import { authFetch } from "../../auth";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import "./status.css";
import "./spending.css";

/** The Spending page: whether auto spending is on, how it splits the kingdom's money, and the funding it holds. */
function SpendingPage(props) {
    return (
        <>
            <Header data={props.data} />
            <Spending kingdom={props.data.kingdom} loading={props.loading} updateData={props.updateData} />
            <HelpButton scrollTarget={"spending"} />
        </>
    );
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
                    <NumberControl
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
                    <NumberControl
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
                    <NumberControl
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
                    <NumberControl
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

export default SpendingPage;
