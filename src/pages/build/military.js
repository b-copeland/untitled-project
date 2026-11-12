import { displayPercent } from "../../format";
import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import { AmountInput } from "../../components/forms";
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Toast from 'react-bootstrap/Toast';
import ToastContainer from 'react-bootstrap/ToastContainer';
import "./military.css";
import Header from "../../components/header";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";

function MilitaryContent(props) {
    const kdInfo = props.data.kingdom;
    const mobisInfo = props.data.mobis;
    return (
    <>
        <Header data={props.data} />
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="recruits"
          justify
          fill
          variant="tabs"
        >
          <Tab eventKey="recruits" title="Recruits">
            <Recruits kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="specialists" title="Specialists">
            <Specialists kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="levy" title="Levy">
            <Levy kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="allocate" title="Allocate">
            <Allocate kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData}/>
          </Tab>
          <Tab eventKey="disband" title="Disband">
            <Disband kdInfo={kdInfo} mobisInfo={mobisInfo} loading={props.loading} updateData={props.updateData} state={props.data.state}/>
          </Tab>
        </Tabs>
        <HelpButton scrollTarget={"military"}/>
    </>
    )
}

function Recruits(props) {
    const [recruitsInput, setRecruitsInput] = useState("");
    const [recruitsResults, setRecruitsResults] = useState([]);
    
    // useEffect(() => {
    //     const fetchData = async () => {
    //         await authFetch("api/settle").then(r => r.json()).then(r => setSettleInfo(r));
    //         setReloading(false);
    //     }
    //     fetchData();
    // }, [reloading])

    const handleRecruitsInput = (e) => {
        setRecruitsInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (recruitsInput > 0) {
            let opts = {
                'recruitsInput': recruitsInput,
            };
            const updateFunc = () => authFetch('api/recruits', {
                method: 'post',
                body: JSON.stringify(opts)
            }).then(r => r.json()).then(r => setRecruitsResults(recruitsResults.concat(r)))
            props.updateData(['mobis', 'kingdom'], [updateFunc]);
            setRecruitsInput('');
        }
    }
    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const price = props.mobisInfo.recruit_price || 0;
    const maxRecruitsNow = Math.min(props.mobisInfo.current_available_recruits || 0, price > 0 ? Math.floor((props.kdInfo.money || 0) / price) : Infinity);
    return (
        <div className="recruits">
            <ResultToasts title="Recruits Results" results={recruitsResults} setResults={setRecruitsResults} />
            <div className="text-box recruits-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Time</span>
                    <span className="text-box-item-value">{(props.mobisInfo.recruit_time / 3600).toFixed(1)}h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Cost</span>
                    <span className="text-box-item-value">{props.mobisInfo.recruit_price?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Hangar Capacity</span>
                    <span className="text-box-item-value">
                        {props.mobisInfo.current_hangar_capacity?.toLocaleString()} / {props.mobisInfo.max_hangar_capacity?.toLocaleString()} ({displayPercent(props.mobisInfo.current_hangar_capacity / props.mobisInfo.max_hangar_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.current_total.recruits?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.hour_24.recruits?.toLocaleString()}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.max_available_recruits?.toLocaleString()}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.current_available_recruits?.toLocaleString()}</span>
                </div>
                <div className="amount-field">
                    <label htmlFor="recruits-input">New recruits</label>
                    <AmountInput name="recruits" id="recruits-input" label="New recruits" value={recruitsInput}
                        onChange={handleRecruitsInput} max={maxRecruitsNow} />
                </div>
                {props.loading.mobis
                ? <Button className="recruits-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="recruits-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Recruit
                </Button>
                }
                {
                    recruitsInput !== ""
                    ? <h3>Recruits Cost: {(parseInt(recruitsInput) * props.mobisInfo.recruit_price).toLocaleString()}</h3>
                    : null
                }
            </div>
        </div>
        )
}

const initialInput = {
    "attack": "",
    "defense": "",
    "flex": "",
    "big_flex": "",
};

function Specialists(props) {
    const [specialistsResults, setSpecialistsResults] = useState([]);
    const [input, setInput] = useState(initialInput)

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput({
          ...input,
          [name]: value,
        });
      };

    const onSubmitClick = (e)=>{
        let opts = input;
        const updateFunc = () => authFetch('api/mobis', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setSpecialistsResults(specialistsResults.concat(r)))
        props.updateData(['mobis', 'kingdom'], [updateFunc]);
    }

    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const calcSpecialistsCosts = (input, units_desc) => {
        var total = 0
        for (const unit in input) {
            total += (parseInt(input[unit] || 0) * units_desc[unit]["cost"]);
        }
        return total
    }
    const calcRecruitsUsed = (input) => {
        var total = 0
        for (const unit in input) {
            total += (parseInt(input[unit] || 0));
        }
        return total
    }
    const specialistCosts = calcSpecialistsCosts(input, props.mobisInfo.units_desc);
    const recruitsUsed = calcRecruitsUsed(input);
    // The most of one unit: the recruits left after the others, and what the money covers after the others.
    const soloTrain = (unit) => {
        const each = props.mobisInfo.units_desc[unit].cost || 0;
        return Math.max(Math.min(props.kdInfo.units.recruits || 0, each > 0 ? Math.floor((props.kdInfo.money || 0) / each) : Infinity), 0);
    };
    const maxTrain = (unit) => {
        const mine = parseInt(input[unit] || 0) || 0;
        const each = props.mobisInfo.units_desc[unit].cost || 0;
        const recruitsLeft = (props.kdInfo.units.recruits || 0) - (recruitsUsed - mine);
        const moneyLeft = each > 0 ? Math.floor(((props.kdInfo.money || 0) - (specialistCosts - mine * each)) / each) : Infinity;
        return Math.max(Math.min(recruitsLeft, moneyLeft), 0);
    };
    return (
        <div className="specialists">
            <ResultToasts title="Recruits Results" results={specialistsResults} setResults={setSpecialistsResults} />
            <div className="text-box box-tight specialists-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Hangar Capacity</span>
                    <span className="text-box-item-value">
                        {props.mobisInfo.current_hangar_capacity?.toLocaleString()} / {props.mobisInfo.max_hangar_capacity?.toLocaleString()} ({displayPercent(props.mobisInfo.current_hangar_capacity / props.mobisInfo.max_hangar_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.current.recruits?.toLocaleString()}</span>
                </div>
            </div>
            <div className="table-scroll"><Table className="specialists-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Cost</th>
                        <th style={{textAlign: "right"}}>Trained</th>
                        <th style={{textAlign: "right"}}>Training</th>
                        {/* <th style={{textAlign: "right"}}>Offense</th>
                        <th style={{textAlign: "right"}}>Defense</th>
                        <th style={{textAlign: "right"}}>Hangar Usage</th>
                        <th style={{textAlign: "right"}}>Fuel</th> */}
                        <th style={{textAlign: "right"}}>To Train</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Attackers</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.attack || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.attack || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="attack" id="attackers-input" label="attack" value={input.attack} onChange={handleInputChange} max={maxTrain("attack")} soloMax={soloTrain("attack")} />
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Defenders</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.defense || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.defense || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="defense" id="defenders-input" label="defense" value={input.defense} onChange={handleInputChange} max={maxTrain("defense")} soloMax={soloTrain("defense")} />
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Flexers</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.flex || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.flex || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="flex" id="flexers-input" label="flex" value={input.flex} onChange={handleInputChange} max={maxTrain("flex")} soloMax={soloTrain("flex")} />
                        }</td>
                    </tr>
                    {
                        props.kdInfo.completed_projects.indexOf('big_flexers') >= 0
                        ? <tr>
                            <td style={{textAlign: "left"}}>Big Flexers</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.cost || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.big_flex || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.big_flex || 0).toLocaleString()}</td>
                            {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.offense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td> */}
                            <td style={{textAlign: "right"}}>{
                                <AmountInput name="big_flex" id="big-flexers-input" label="big_flex" value={input.big_flex} onChange={handleInputChange} max={maxTrain("big_flex")} soloMax={soloTrain("big_flex")} />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td style={{textAlign: "left"}}>Big Flexers</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.cost || 0).toLocaleString()}</td>
                            <td colSpan={2}>Research "Big Flexers" Project to Unlock</td>
                            {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.offense || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td> */}
                            <td style={{textAlign: "right"}}>{
                                <AmountInput name="big_flex" id="big-flexers-input" label="big_flex" value={input.big_flex} onChange={handleInputChange} max={maxTrain("big_flex")} soloMax={soloTrain("big_flex")} disabled />
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table></div>
            {
                props.loading.mobis
                ? <Button className="specialists-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="specialists-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Train
                </Button>
            }
            {
                recruitsUsed != 0
                ? <div>
                    <h3>Training Cost: {specialistCosts.toLocaleString()}</h3>
                    <h3>Recruits Remaining: {(props.kdInfo.units.recruits - recruitsUsed).toLocaleString()}</h3>
                </div>
                : null
            }
        </div>
    
    )
}

function Levy(props) {
    return (
        <div>
            <h2>Levy</h2>
            <h3>Coming Soon...</h3>
        </div>
    )
}
function Allocate(props) {
    const [specialistsResults, setSpecialistsResults] = useState([]);
    const [input, setInput] = useState(initialInput);
    const [maxRecruits, setMaxRecruits] = useState(props.kdInfo.max_recruits || "");
    const [recruitsBeforeUnits, setRecruitsBeforeUnits] = useState(props.kdInfo?.recruits_before_units)

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput({
          ...input,
          [name]: value,
        });
      };
    const handleMaxRecruitsInput = (e) => {
        setMaxRecruits(e.target.value);
    }

    const onSubmitClick = (e)=>{
        let opts = {
            "max_recruits": maxRecruits,
            "targets": input,
        };
        const updateFunc = () => authFetch('api/mobis/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setSpecialistsResults(specialistsResults.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
    }
    const handleEnabledChange = (e) => {
        let opts = {
            'recruits_before_units': e.target.checked
        }
        const updateFunc = () => authFetch('api/mobis/target', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => {setSpecialistsResults(specialistsResults.concat(r))})
        props.updateData(['kingdom'], [updateFunc])
        setRecruitsBeforeUnits(e.target.checked)
    }

    // A unit's slider can go as far as is left of 100% once the other units' new numbers are counted.
    const maxAllocate = (unit) => Math.max(100 - Object.entries(input).filter(([other]) => other !== unit).reduce((sum, [, value]) => sum + (parseFloat(value) || 0), 0), 0);
    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    return (
        <div className="specialists">
            <ResultToasts title="Recruits Results" results={specialistsResults} setResults={setSpecialistsResults} />
            <div className="text-box box-tight specialists-box">
                <span>Choose the target allocation of units that you would like the auto-spender to build towards</span>
            </div>
            <Form>
                <Form.Check 
                    type="switch"
                    id="recruits-before-units-switch"
                    label="Train Recruits before Units?"
                    defaultChecked={recruitsBeforeUnits}
                    onChange={handleEnabledChange}
                    disabled={props.loading.kingdom}
                />
            </Form>
            <InputGroup className="max-recruits-input-group">
                <InputGroup.Text id="recruits-input-display">
                    Max Recruits
                </InputGroup.Text>
                <Form.Control 
                    id="recruits-input"
                    onChange={handleMaxRecruitsInput}
                    value={maxRecruits || ""} 
                    placeholder="0"
                    autoComplete="off"
                />
            </InputGroup>
            <div className="table-scroll"><Table className="specialists-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Cost</th>
                        <th style={{textAlign: "right"}}>Trained</th>
                        <th style={{textAlign: "right"}}>Training</th>
                        {/* <th style={{textAlign: "right"}}>Offense</th>
                        <th style={{textAlign: "right"}}>Defense</th>
                        <th style={{textAlign: "right"}}>Hangar Usage</th>
                        <th style={{textAlign: "right"}}>Fuel</th> */}
                        <th style={{textAlign: "right"}}>Current Allocation</th>
                        <th style={{textAlign: "right"}}>New Allocation</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style={{textAlign: "left"}}>Attackers</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.attack || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.attack || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.attack.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{displayPercent((props.kdInfo.units_target?.attack || 0))}</td>
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="attack" id="attackers-input" label="attack" value={input.attack} onChange={handleInputChange} suffix="%" max={maxAllocate("attack")} soloMax={100} />
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Defenders</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.defense || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.defense || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.defense.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{displayPercent((props.kdInfo.units_target?.defense || 0))}</td>
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="defense" id="defenders-input" label="defense" value={input.defense} onChange={handleInputChange} suffix="%" max={maxAllocate("defense")} soloMax={100} />
                        }</td>
                    </tr>
                    <tr>
                        <td style={{textAlign: "left"}}>Flexers</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.cost || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.flex || 0).toLocaleString()}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.flex || 0).toLocaleString()}</td>
                        {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.offense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.defense || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.hangar_capacity || 0)}</td>
                        <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.flex.fuel || 0)}</td> */}
                        <td style={{textAlign: "right"}}>{displayPercent((props.kdInfo.units_target?.flex || 0))}</td>
                        <td style={{textAlign: "right"}}>{
                            <AmountInput name="flex" id="flexers-input" label="flex" value={input.flex} onChange={handleInputChange} suffix="%" max={maxAllocate("flex")} soloMax={100} />
                        }</td>
                    </tr>
                    {
                        props.kdInfo.completed_projects.indexOf('big_flexers') >= 0
                        ? <tr>
                            <td style={{textAlign: "left"}}>Big Flexers</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.cost || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units.current_total.big_flex || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units.hour_24.big_flex || 0).toLocaleString()}</td>
                            {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.offense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td> */}
                            <td style={{textAlign: "right"}}>{displayPercent((props.kdInfo.units_target?.big_flex || 0))}</td>
                            <td style={{textAlign: "right"}}>{
                                <AmountInput name="big_flex" id="big-flexers-input" label="big_flex" value={input.big_flex} onChange={handleInputChange} suffix="%" max={maxAllocate("big_flex")} soloMax={100} />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td style={{textAlign: "left"}}>Big Flexers</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.cost || 0).toLocaleString()}</td>
                            <td colSpan={2}>Research "Big Flexers" Project to Unlock</td>
                            {/* <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.offense || 0).toLocaleString()}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td style={{textAlign: "right"}}>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td> */}
                            <td style={{textAlign: "right"}}>{displayPercent((props.kdInfo.units_target?.big_flex || 0))}</td>
                            <td style={{textAlign: "right"}}>{
                                <AmountInput name="big_flex" id="big-flexers-input" label="big_flex" value={input.big_flex} onChange={handleInputChange} suffix="%" max={maxAllocate("big_flex")} soloMax={100} disabled />
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table></div>
            {
                props.loading.kingdom
                ? <Button className="specialists-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="specialists-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Update
                </Button>
            }
        </div>
    
    )
}
function Disband(props) {
    const [results, setResults] = useState([]);
    const [input, setInput] = useState({});

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setInput((prev) => ({
          ...prev,
          [name]: value,
        }));
      };
    const onSubmitClick = (e)=>{
        let opts = {
            "input": input,
        };
        const updateFunc = () => authFetch('api/mobis/disband', {
            method: 'post',
            body: JSON.stringify(opts)
        }).then(r => r.json()).then(r => setResults(results.concat(r)))
        props.updateData(['kingdom'], [updateFunc]);
        setInput({});
    }

    const units = props.kdInfo.units || {};
    const disbandRows = Object.keys(units).map((unitKey, iter) => {
        const prettyNames = props.state.pretty_names || {};
        if (unitKey == "engineers") {
            return null;
        }
        return <tr key={"disband_" + iter}>
            <td style={{textAlign: "left"}}>{prettyNames[unitKey] || unitKey}</td>
            <td style={{textAlign: "right"}}>{units[unitKey] || 0}</td>
            <td style={{textAlign: "right"}}>{
                <AmountInput name={unitKey} id={"disband-" + unitKey} label={prettyNames[unitKey] || unitKey}
                    value={input[unitKey]} onChange={handleInputChange} max={Math.floor(units[unitKey] || 0)} />
            }</td>
        </tr>
    })
    
    return (
        <div className="col-center military-disband">
            <h2>Disband Units</h2>
            <div className="text-box box-tight specialists-box">
                <span>Disband units to return them to your population and receive {displayPercent(props.state.game_config?.BASE_DISBAND_COST_RETURN || 0)} of the training cost back</span>
            </div>
            <ResultToasts title="Disband Results" results={results} setResults={setResults} />
            <div className="table-scroll"><Table className="specialists-table" striped bordered hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Unit</th>
                        <th style={{textAlign: "right"}}>Available</th>
                        <th style={{textAlign: "right"}}>To Disband</th>
                    </tr>
                </thead>
                <tbody>
                    {disbandRows}
                </tbody>
            </Table></div>
            {
                props.loading.kingdom
                ? <Button className="specialists-button" variant="warning" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="specialists-button" variant="warning" type="submit" onClick={onSubmitClick}>
                    Disband
                </Button>
            }
        </div>
    )
}

export default MilitaryContent;