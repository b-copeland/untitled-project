import React, { useState } from "react";
import Form from 'react-bootstrap/Form';
import { NumberControl } from "../../components/forms";
import InputGroup from 'react-bootstrap/InputGroup';
import Button from 'react-bootstrap/Button';
import Table from 'react-bootstrap/Table';
import { authFetch } from "../../auth";
import { displayPercent } from "../../format";
import HelpButton from "../../components/helpbutton";
import { ResultToasts } from "../../components/results";
import "./status.css";
import "./shields.css";

/** The Shields page: the shields the kingdom pays fuel for, and the form to change them. */
function ShieldsPage(props) {
    return (
        <>
            <Shields data={props.data} loading={props.loading} updateData={props.updateData} />
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
            <div className="table-scroll">
            <Table className="shields-table" hover size="sm">
                <thead>
                    <tr>
                        <th style={{textAlign: "left"}}>Shield</th>
                        <th style={{textAlign: "right"}}>Current %</th>
                        <th style={{textAlign: "right"}}>Max %</th>
                        <th style={{textAlign: "right"}}>Current Power Cost</th>
                        <th style={{textAlign: "right"}}>Max Power Cost</th>
                        <th style={{textAlign: "right"}}>New %</th>
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
                            <InputGroup size="sm" className="shields-input-group">
                                <NumberControl
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
                            <InputGroup size="sm" className="shields-input-group">
                                <NumberControl
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
                            <InputGroup size="sm" className="shields-input-group">
                                <NumberControl
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
                            <InputGroup size="sm" className="shields-input-group">
                                <NumberControl
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
            </div>
            <div className="form-actions">
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
        </div>
    )
}

export default ShieldsPage;
