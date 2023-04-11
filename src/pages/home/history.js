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
    return (
        <h2>Coming Soon...</h2>
    )
}

export default HistoryContent;