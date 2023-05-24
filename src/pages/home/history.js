import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import 'bootstrap/dist/css/bootstrap.css';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./history.css";
import Header from "../../components/header";
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { FilterMatchMode } from 'primereact/api';
import "primereact/resources/primereact.min.css";
import "primereact/resources/themes/bootstrap4-dark-blue/theme.css";     
import "primeicons/primeicons.css";
import 'bootstrap/dist/css/bootstrap.css';
import HelpButton from "../../components/helpbutton";
import Select from 'react-select';
import {VictoryZoomContainer, VictoryBrushContainer, VictoryChart, VictoryLine, VictoryAxis, VictoryTooltip, VictoryVoronoiContainer} from 'victory';

function getTimeSinceString(date) {
    if (date === undefined) {
        return "--"
    }
    const hours = Math.floor(Math.abs(Date.now() - Date.parse(date)) / 3.6e6);
    const days = Math.floor(hours / 24);
    if (hours > 48) {
        return days.toString() + 'd'
    }
    return hours.toString() + 'h';
}

function getNiceTimeString(date) {
    if (date === undefined) {
        return "--"
    }
    const dateParse = new Date(date);

    const options = { weekday: 'short', month: 'short', day: 'numeric'};
    return dateParse.toLocaleString('en-us', options);
}

function getHoursSince(dateStr) {
    if (dateStr === undefined) {
        return "--"
    }
    const hours = Math.floor(Math.abs(Date.now() - Date.parse(dateStr)) / 3.6e6);
    return hours
}

function HistoryContent(props) {
    const [key, setKey] = useState('attack');

    if (Object.keys(props.data.galaxies_inverted).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdoms).length === 0) {
        return null;
    }
    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="attack"
        justify
        fill
        variant="tabs"
      >
        <Tab eventKey="attack" title="Attack">
          <Attack kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} attackhistory={props.data.attackhistory} loading={props.loading}/>
        </Tab>
        <Tab eventKey="spy" title="Spy">
          <Spy kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} spyhistory={props.data.spyhistory} loading={props.loading} />
        </Tab>
        <Tab eventKey="missiles" title="Missiles">
          <Missiles kingdoms={props.data.kingdoms} galaxies_inverted={props.data.galaxies_inverted} missilehistory={props.data.missilehistory} loading={props.loading}/>
        </Tab>
        <Tab eventKey="stats" title="Stats">
          <Stats />
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"history"}/>
    </>
    )
}

function Attack(props) {
    const [filters, setFilters] = useState({
        time: { value: null, matchMode: FilterMatchMode.CONTAINS },
        day: { value: null, matchMode: FilterMatchMode.CONTAINS },
        time_since: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        to: { value: null, matchMode: FilterMatchMode.CONTAINS },
        news: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });
    if (props.loading.attackhistory) {
        return <h2>Loading...</h2>;
    }
    const newsRowsPrime = props.attackhistory.map((newsItem) => {
            return {
                "time": new Date(newsItem.time).toLocaleString(),
                "day": getNiceTimeString(newsItem.time),
                "time_since": getHoursSince(newsItem.time),
                "to": (newsItem.to != "") ? props.kingdoms[newsItem.to] + ' (' + props.galaxies_inverted[newsItem.to] + ')' : "",
                "news": newsItem.news,
            }
        }
    );
    return (
        <div className="kingdom">
            <DataTable
                value={newsRowsPrime}
                paginator
                size="small"
                columnResizeMode="expand"
                rows={10}
                rowsPerPageOptions={[5, 10, 25, 50]}
                sortMode="multiple"
                removableSort
                filters={filters}
                filterDisplay="row"
                style={{ width: '100%'}}
                header={"Attack History"}
            >
                <Column field="time" header="Time" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="news" header="News" filter showFilterMenu={false} style={{ width: '60%' }}/>
                {/* <Column field="day" header="Day" sortable filter showFilterMenu={false} style={{ width: '10%' }}/> */}
                <Column field="to" header="To" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="time_since" header="Hours Since" dataType="numeric" filter style={{ width: '10%' }}/>
            </DataTable>
        </div>
    );
}

function Spy(props) {
    const [filters, setFilters] = useState({
        time: { value: null, matchMode: FilterMatchMode.CONTAINS },
        day: { value: null, matchMode: FilterMatchMode.CONTAINS },
        time_since: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        to: { value: null, matchMode: FilterMatchMode.CONTAINS },
        operation: { value: null, matchMode: FilterMatchMode.CONTAINS },
        news: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });
    if (props.loading.spyhistory) {
        return <h2>Loading...</h2>;
    }
    const newsRowsPrime = props.spyhistory.map((newsItem) => {
            return {
                "time": new Date(newsItem.time).toLocaleString(),
                "day": getNiceTimeString(newsItem.time),
                "time_since": getHoursSince(newsItem.time),
                "to": (newsItem.to != "") ? props.kingdoms[newsItem.to] + ' (' + props.galaxies_inverted[newsItem.to] + ')' : "",
                "operation": newsItem.operation,
                "news": newsItem.news,
            }
        }
    );
    return (
        <div className="kingdom">
            <DataTable
                value={newsRowsPrime}
                paginator
                size="small"
                columnResizeMode="expand"
                rows={10}
                rowsPerPageOptions={[5, 10, 25, 50]}
                sortMode="multiple"
                removableSort
                filters={filters}
                filterDisplay="row"
                style={{ width: '100%'}}
                header={"Spy History"}
            >
                <Column field="time" header="Time" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="news" header="News" filter showFilterMenu={false} style={{ width: '45%'}}/>
                {/* <Column field="day" header="Day" sortable filter showFilterMenu={false} style={{ width: '10%' }}/> */}
                <Column field="to" header="To" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="operation" header="Operation" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="time_since" header="Hours Since" dataType="numeric" filter style={{ width: '10%' }}/>
            </DataTable>
        </div>
    );
}

function Missiles(props) {
    const [filters, setFilters] = useState({
        time: { value: null, matchMode: FilterMatchMode.CONTAINS },
        day: { value: null, matchMode: FilterMatchMode.CONTAINS },
        time_since: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        to: { value: null, matchMode: FilterMatchMode.CONTAINS },
        news: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });
    if (props.loading.missilehistory) {
        return <h2>Loading...</h2>;
    }
    const newsRowsPrime = props.missilehistory.map((newsItem) => {
            return {
                "time": new Date(newsItem.time).toLocaleString(),
                "day": getNiceTimeString(newsItem.time),
                "time_since": getHoursSince(newsItem.time),
                "to": (newsItem.to != "") ? props.kingdoms[newsItem.to] + ' (' + props.galaxies_inverted[newsItem.to] + ')' : "",
                "news": newsItem.news,
            }
        }
    );
    return (
        <div className="kingdom">
            <DataTable
                value={newsRowsPrime}
                paginator
                size="small"
                columnResizeMode="expand"
                rows={10}
                rowsPerPageOptions={[5, 10, 25, 50]}
                sortMode="multiple"
                removableSort
                filters={filters}
                filterDisplay="row"
                style={{ width: '100%'}}
                header={"Missile History"}
            >
                <Column field="time" header="Time" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="news" header="News" filter showFilterMenu={false} style={{ width: '60%' }}/>
                {/* <Column field="day" header="Day" sortable filter showFilterMenu={false} style={{ width: '10%' }}/> */}
                <Column field="to" header="To" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="time_since" header="Hours Since" sortable dataType="numeric" filter style={{ width: '10%' }}/>
            </DataTable>
        </div>
    );
}

function Stats(props) {
    const [loading, setLoading] = useState(true);
    const [history, setHistory] = useState({});
    // const [zoomDomain, setZoomDomain] = useState();
    // const [brushDomain, setBrushDomain] = useState();
    const [selected, setSelected] = useState("networth");

    useEffect(() => {
        authFetch('api/history').then(
            r => r.json()
        ).then(r => {setHistory(r);setLoading(false)}).catch(
            err => {
                console.log('Failed to fetch history');
                console.log(err);
            }
        );
    }, []);

    const handleChange = (selectedOption) => {
        setSelected(selectedOption.value);
    };
    if (loading) {
        return <h2>Loading...</h2>
    };

    const statOptions = [
        {value: "networth", "label": "Networth"},
        {value: "stars", "label": "Stars"},
        {value: "population", "label": "Population"},
        {value: "drones", "label": "Drones"},
        {value: "engineers", "label": "Engineers"},
        {value: "max_offense", "label": "Max Offense"},
        {value: "max_defense", "label": "Max Defense"},
    ];

    const data = history[selected].map((histItem) => {
        return {
            x: new Date(histItem.time),
            y: histItem.value,
            label: histItem.value.toLocaleString(),
        }
    })
    const maxY = Math.max(...data.map(o => o.y))
    return (
        <div className="stat-history">
            <form className="select-stat-form">
                <label id="aria-label" htmlFor="aria-example-input">
                    Select a stat
                </label>
                <Select
                    id="select-stat"
                    className="stat-select"
                    options={statOptions}
                    onChange={handleChange}
                    autoFocus={selected == undefined}
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
            </form>
            <VictoryChart
                width={900}
                height={300}
                padding={{left: 70, bottom: 30}}
                domain={{y: [0, maxY]}}
                domainPadding={20}
                scale={{x: "time", y: "linear"}}
                containerComponent={
                    <VictoryVoronoiContainer responsive={true}
                    // zoomDimension="x"
                    // zoomDomain={zoomDomain}
                    // onZoomDomainChange={setZoomDomain}
                    />
                }
                style={{
                    data: {stroke: "cyan"},
                    parent: { border: "1px solid #ccc", padding: "10px"},
                }}
            >
                <VictoryAxis
                    label="Time" 
                    style={{
                        axis: {
                            stroke: 'white'  //CHANGE COLOR OF Y-AXIS
                        },
                        tickLabels: {
                            fill: 'white' //CHANGE COLOR OF Y-AXIS LABELS
                        },
                    }}    
                />
                <VictoryAxis
                    dependentAxis
                    label="Value" 
                    style={{
                        axis: {
                            stroke: 'white'  //CHANGE COLOR OF Y-AXIS
                        },
                        tickLabels: {
                            fill: 'white' //CHANGE COLOR OF Y-AXIS LABELS
                        },
                    }}
                />
                <VictoryLine
                    style={{
                        data: {stroke: "cyan"},
                        tickLabels: {fill: "white"},
                        labels: {fill: "black"},
                    }}
                    labelComponent={<VictoryTooltip flyoutStyle={{fill: "white"}}/>}
                    data={data}
                    x="x"
                    y="y"
                />
            
            </VictoryChart>
            
            {/* <VictoryChart
                width={900}
                height={90}
                scale={{x: "time"}}
                padding={{top: 0, left: 50, right: 50, bottom: 30}}
                containerComponent={
                    <VictoryBrushContainer responsive={false}
                    brushStyle={{
                        fill: "gray",
                        opacity: 0.2,
                    }}
                    brushDimension="x"
                    brushDomain={brushDomain}
                    onBrushDomainChange={setZoomDomain}
                    />
                }
            >
                <VictoryAxis
                    tickValues={nwData.map((nwItem) => new Date(nwItem.time))}
                    // tickValues={[
                    //   new Date(1985, 1, 1),
                    //   new Date(1990, 1, 1),
                    //   new Date(1995, 1, 1),
                    //   new Date(2000, 1, 1),
                    //   new Date(2005, 1, 1),
                    //   new Date(2010, 1, 1),
                    //   new Date(2015, 1, 1)
                    // ]}
                    tickFormat={(x) => new Date(x).toLocaleString()}
                    style={{
                        data: {stroke: "cyan"},
                        tickLabels: {fill: "white"}
                    }}
                />
                <VictoryLine
                    style={{
                        data: {stroke: "cyan"},
                        tickLabels: {fill: "white"}
                    }}
                    data={nwData}
                    x="x"
                    y="value"
                />
            </VictoryChart> */}
        </div>
      );
}

export default HistoryContent;