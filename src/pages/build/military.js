import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import InputGroup from 'react-bootstrap/InputGroup';
import Form from 'react-bootstrap/Form';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import "./military.css";

function MilitaryContent() {
    const [kdInfo, setKdInfo] = useState({});
    const [mobisInfo, setMobisInfo] = useState({});
    const [reloading, setReloading] = useState(false);
    
    useEffect(() => {
        const fetchData = async () => {
            await authFetch("api/kingdom").then(r => r.json()).then(r => setKdInfo(r));
            await authFetch("api/mobis").then(r => r.json()).then(r => setMobisInfo(r));
            setReloading(false);
        }
        fetchData();
    }, [reloading])

    return (
        <Tabs
          id="controlled-tab-example"
          defaultActiveKey="recruits"
          justify
          fill
          variant="tabs"
        >
          <Tab eventKey="recruits" title="Recruits">
            <Recruits kdInfo={kdInfo} mobisInfo={mobisInfo} reloading={reloading} setReloading={v => setReloading(v)}/>
          </Tab>
          <Tab eventKey="specialists" title="Specialists">
            <Specialists kdInfo={kdInfo} mobisInfo={mobisInfo} reloading={reloading} setReloading={v => setReloading(v)}/>
          </Tab>
          <Tab eventKey="levy" title="Levy">
            <Levy kdInfo={kdInfo} mobisInfo={mobisInfo} reloading={reloading} setReloading={v => setReloading(v)}/>
          </Tab>
        </Tabs>
    )
}

function Recruits(props) {
    const [recruitsInput, setRecruitsInput] = useState();
    
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
            authFetch('api/recruits', {
                method: 'post',
                body: JSON.stringify(opts)
            });
            props.setReloading(true);
        }
    }
    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div className="recruits">
            <div className="text-box recruits-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Time</span>
                    <span className="text-box-item-value">12h</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Recruit Cost</span>
                    <span className="text-box-item-value">{props.mobisInfo.recruit_price}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Hangar Capacity</span>
                    <span className="text-box-item-value">
                        {props.mobisInfo.current_hangar_capacity} / {props.mobisInfo.max_hangar_capacity} ({displayPercent(props.mobisInfo.current_hangar_capacity / props.mobisInfo.max_hangar_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.current_total.recruits}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Training Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.hour_24.recruits}</span>
                </div>
                <br />
                <div className="text-box-item">
                    <span className="text-box-item-title">Maximum New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.max_available_recruits}</span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Available New Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.current_available_recruits}</span>
                </div>
                <InputGroup className="recruits-input-group">
                    <InputGroup.Text id="recruits-input-display">
                        New Recruits
                    </InputGroup.Text>
                    <Form.Control 
                        id="recruits-input"
                        onChange={handleRecruitsInput}
                        value={recruitsInput || ""} 
                        placeholder="0"
                    />
                </InputGroup>
                {props.reloading
                ? <Button className="recruits-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="recruits-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Recruit
                </Button>
                }
            </div>
        </div>
        )
}

function Specialists(props) {
    const [attackersInput, setAttackersInput] = useState('');
    const [defendersInput, setDefendersInput] = useState('');
    const [flexersInput, setFlexersInput] = useState('');
    const [bigFlexersInput, setBigFlexersInput] = useState('');

    const handleAttackersInput = (e) => {
        setAttackersInput(e.target.value);
    }
    const handleDefendersInput = (e) => {
        setDefendersInput(e.target.value);
    }
    const handleFlexersInput = (e) => {
        setFlexersInput(e.target.value);
    }
    const handleBigFlexersInput = (e) => {
        setBigFlexersInput(e.target.value);
    }

    const onSubmitClick = (e)=>{
        if (
            attackersInput || defendersInput || flexersInput
        ) {
            let opts = {
                'attack': attackersInput === '' ? undefined : attackersInput,
                'defense': defendersInput === '' ? undefined : defendersInput,
                'flex': flexersInput === '' ? undefined : flexersInput,
                'big_flex': bigFlexersInput === '' ? undefined : bigFlexersInput,
            };
            authFetch('api/mobis', {
                method: 'post',
                body: JSON.stringify(opts)
            });
            props.setReloading(true);
        }
    }

    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    if (Object.keys(props.mobisInfo).length === 0) {
        return null;
    }
    if (Object.keys(props.kdInfo).length === 0) {
        return null;
    }
    return (
        <div className="specialists">
            <div className="text-box specialists-box">
                <div className="text-box-item">
                    <span className="text-box-item-title">Hangar Capacity</span>
                    <span className="text-box-item-value">
                        {props.mobisInfo.current_hangar_capacity} / {props.mobisInfo.max_hangar_capacity} ({displayPercent(props.mobisInfo.current_hangar_capacity / props.mobisInfo.max_hangar_capacity)})
                    </span>
                </div>
                <div className="text-box-item">
                    <span className="text-box-item-title">Current Recruits</span>
                    <span className="text-box-item-value">{props.mobisInfo.units.current.recruits}</span>
                </div>
            </div>
            <Table className="specialists-table" striped bordered hover>
                <thead>
                    <tr>
                        <th>Unit</th>
                        <th>Cost</th>
                        <th>Trained</th>
                        <th>Training</th>
                        <th>Offense</th>
                        <th>Defense</th>
                        <th>Hangar Usage</th>
                        <th>Fuel</th>
                        <th>To Train</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Attackers</td>
                        <td>{(props.mobisInfo.units_desc.attack.cost || 0)}</td>
                        <td>{(props.mobisInfo.units.current_total.attack || 0)}</td>
                        <td>{(props.mobisInfo.units.hour_24.attack || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.attack.offense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.attack.defense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.attack.hangar_capacity || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.attack.fuel || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="specialists-form"
                                id="attackers-input"
                                onChange={handleAttackersInput}
                                value={attackersInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Defenders</td>
                        <td>{(props.mobisInfo.units_desc.defense.cost || 0)}</td>
                        <td>{(props.mobisInfo.units.current_total.defense || 0)}</td>
                        <td>{(props.mobisInfo.units.hour_24.defense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.defense.offense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.defense.defense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.defense.hangar_capacity || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.defense.fuel || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="specialists-form"
                                id="defenders-input"
                                onChange={handleDefendersInput}
                                value={defendersInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    <tr>
                        <td>Flexers</td>
                        <td>{(props.mobisInfo.units_desc.flex.cost || 0)}</td>
                        <td>{(props.mobisInfo.units.current_total.flex || 0)}</td>
                        <td>{(props.mobisInfo.units.hour_24.flex || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.flex.offense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.flex.defense || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.flex.hangar_capacity || 0)}</td>
                        <td>{(props.mobisInfo.units_desc.flex.fuel || 0)}</td>
                        <td>{
                            <Form.Control 
                                className="specialists-form"
                                id="flexers-input"
                                onChange={handleFlexersInput}
                                value={flexersInput || ""} 
                                placeholder="0"
                            />
                        }</td>
                    </tr>
                    {
                        props.kdInfo.completed_projects.indexOf('big_flexers') >= 0
                        ? <tr>
                            <td>Big Flexers</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.cost || 0)}</td>
                            <td>{(props.mobisInfo.units.current_total.big_flex || 0)}</td>
                            <td>{(props.mobisInfo.units.hour_24.big_flex || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.offense || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="specialists-form"
                                    id="big-flexers-input"
                                    onChange={handleBigFlexersInput}
                                    value={bigFlexersInput || ""} 
                                    placeholder="0"
                                />
                            }</td>
                        </tr>
                        : <tr className="disabled-table-row">
                            <td>Big Flexers</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.cost || 0)}</td>
                            <td colSpan={2}>Research "Big Flexers" Project to Unlock</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.offense || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.defense || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.hangar_capacity || 0)}</td>
                            <td>{(props.mobisInfo.units_desc.big_flex.fuel || 0)}</td>
                            <td>{
                                <Form.Control 
                                    className="specialists-form"
                                    id="big-flexers-input"
                                    onChange={handleBigFlexersInput}
                                    value={bigFlexersInput || ""} 
                                    placeholder="0"
                                    disabled
                                />
                            }</td>
                        </tr>
                    }
                </tbody>
            </Table>
            {
                props.reloading
                ? <Button className="specialists-button" variant="primary" type="submit" disabled>
                    Loading...
                </Button>
                : <Button className="specialists-button" variant="primary" type="submit" onClick={onSubmitClick}>
                    Train
                </Button>
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

export default MilitaryContent;