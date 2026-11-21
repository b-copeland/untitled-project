import React, { useState } from "react";
import Form from 'react-bootstrap/Form';
import { NumberControl } from "../../components/forms";
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import { authFetch } from "../../auth";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import { Panel, FieldRow, Stats } from "../../components/planner";
import "./status.css";
import "./spending.css";

/** The Spending page: whether auto spending is on, how it splits the kingdom's money, and the funding it holds. */
function SpendingPage(props) {
    return (
        <>
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
        <div className="spending panel-grid">
            <ResultToasts title="Auto Spending Results" results={results} setResults={setResults} />
            <Panel title="Auto spending">
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
                <FieldRow label="Settle" hint={`Now ${spendingInfo.settle * 100}%`} htmlFor="settle-percent">
                    <InputGroup size="sm" className="spending-input">
                        <NumberControl
                            id="settle-percent"
                            onChange={handleSettleInput}
                            value={settleInput}
                            placeholder={spendingInfo.settle * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text>%</InputGroup.Text>
                    </InputGroup>
                </FieldRow>
                <FieldRow label="Structures" hint={`Now ${spendingInfo.structures * 100}%`} htmlFor="structures-percent">
                    <InputGroup size="sm" className="spending-input">
                        <NumberControl
                            id="structures-percent"
                            onChange={handleStructuresInput}
                            value={structuresInput}
                            placeholder={spendingInfo.structures * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text>%</InputGroup.Text>
                    </InputGroup>
                </FieldRow>
                <FieldRow label="Military" hint={`Now ${spendingInfo.military * 100}%`} htmlFor="military-percent">
                    <InputGroup size="sm" className="spending-input">
                        <NumberControl
                            id="military-percent"
                            onChange={handleMilitaryInput}
                            value={militaryInput}
                            placeholder={spendingInfo.military * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text>%</InputGroup.Text>
                    </InputGroup>
                </FieldRow>
                <FieldRow label="Engineers" hint={`Now ${spendingInfo.engineers * 100}%`} htmlFor="engineers-percent">
                    <InputGroup size="sm" className="spending-input">
                        <NumberControl
                            id="engineers-percent"
                            onChange={handleEngineersInput}
                            value={engineersInput}
                            placeholder={spendingInfo.engineers * 100}
                            autoComplete="off"
                        />
                        <InputGroup.Text>%</InputGroup.Text>
                    </InputGroup>
                </FieldRow>
                <div className="form-actions spending-actions">
                    {props.loading.kingdom
                    ? <Button className="spending-button" variant="primary" type="submit" disabled>
                        Loading...
                    </Button>
                    : <Button className="spending-button" variant="primary" type="submit" onClick={onSubmitClick}>
                        Submit
                    </Button>
                    }
                </div>
            </Panel>
            <Panel title="Auto spending funding">
                <Stats items={["settle", "structures", "military", "engineers"].map((key) => ({
                    label: key.charAt(0).toUpperCase() + key.slice(1),
                    value: Math.floor(props.kingdom.funding?.[key] || 0).toLocaleString(),
                }))} />
            </Panel>
        </div>
    )
}

export default SpendingPage;
