import React, { useEffect, useState } from "react";
import {login, authFetch, useAuth, logout, getSession, getSessionState} from "../../auth";
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import Table from 'react-bootstrap/Table';
import "./news.css"
import Header from "../../components/header";
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { FilterMatchMode } from 'primereact/api';
import "primereact/resources/primereact.min.css";
import "primereact/resources/themes/bootstrap4-dark-blue/theme.css";     
import "primeicons/primeicons.css";
import 'bootstrap/dist/css/bootstrap.css';
import HelpButton from "../../components/helpbutton";

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

const getNotifsCount = (notifs, categories) => {
  var total = 0;
  for (const category of categories) {
    total += parseInt(notifs[category]);
  }
  return total;
}

const getNotifsSuffix = (notifs, categories) => {
  const count = getNotifsCount(notifs, categories);
  if (count > 0) {
    return ` (${count})`
  } else {
    return ""
  }
}

function NewsContent(props) {
    const [key, setKey] = useState('kingdom');

    const clearNotifs = (categories) => {
        const updateFunc = () => {
            authFetch("api/clearnotifs", {
                method: "POST",
                body: JSON.stringify({"categories": categories})
            });
        }
        props.updateData(['notifs'], [updateFunc])
    }
    useEffect(() => {
        clearNotifs(["news_kingdom"])
    }, [])

    if (Object.keys(props.data.galaxies_inverted).length === 0) {
        return null;
    }
    if (Object.keys(props.data.kingdoms).length === 0) {
        return null;
    }
    const handleNotifsSelect = (eventKey) => {
        if (eventKey === "kingdom") {
            if (props.data.notifs.news_kingdom > 0) {
                clearNotifs(["news_kingdom"])
            }
        } else if (eventKey === "galaxy") {
            if (props.data.notifs.news_galaxy > 0) {
                clearNotifs(["news_galaxy"])
            }
        }
        setKey(eventKey);
    }
    const kdNames = props.data.kingdoms;
    const galaxyMap = props.data.galaxies_inverted;
    return (
    <>
      <Header data={props.data} />
      <Tabs
        id="controlled-tab-example"
        defaultActiveKey="kingdom"
        justify
        fill
        variant="tabs"
        onSelect={(k) => handleNotifsSelect(k)}
      >
        <Tab eventKey="kingdom" title={`Kingdom${getNotifsSuffix(props.data.notifs, ["news_kingdom"])}`}>
          <Kingdom kdNames={kdNames} galaxyMap={galaxyMap} news={props.data.news}/>
        </Tab>
        <Tab eventKey="galaxy" title={`Galaxy${getNotifsSuffix(props.data.notifs, ["news_galaxy"])}`}>
          <Galaxy kdNames={kdNames} galaxyMap={galaxyMap} galaxynews={props.data.galaxynews}/>
        </Tab>
        <Tab eventKey="empire" title="Empire">
          <Empire kdNames={kdNames} galaxyMap={galaxyMap} empirenews={props.data.empirenews}/>
        </Tab>
        <Tab eventKey="universe" title="Universe">
          <Universe universenews={props.data.universenews}/>
        </Tab>
      </Tabs>
      <HelpButton scrollTarget={"news"}/>
    </>
    );
}

function getHoursSince(dateStr) {
    if (dateStr === undefined) {
        return "--"
    }
    const hours = Math.floor(Math.abs(Date.now() - Date.parse(dateStr)) / 3.6e6);
    return hours
}

function Kingdom(props) {
    const [filters, setFilters] = useState({
        time: { value: null, matchMode: FilterMatchMode.CONTAINS },
        day: { value: null, matchMode: FilterMatchMode.CONTAINS },
        time_since: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        from: { value: null, matchMode: FilterMatchMode.CONTAINS },
        news: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });

    if (props.news.length === 0) {
        return null;
    }
    const news = props.news;
    const newsRowsPrime = news.map((newsItem) => {
            return {
                "time": new Date(newsItem.time).toLocaleString(),
                "day": getNiceTimeString(newsItem.time),
                "time_since": getHoursSince(newsItem.time),
                "from": (newsItem.from != "") ? props.kdNames[newsItem.from] + ' (' + props.galaxyMap[newsItem.from] + ')' : "",
                "news": newsItem.news,
            }
        }
    );
    return (
        <div className="kingdom">
            <DataTable
                className="news-table"
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
                header={"Kingdom News"}
            >
                <Column field="time" header="Time" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="news" header="News" filter showFilterMenu={false} style={{ width: '55%' }}/>
                {/* <Column field="day" header="Day" sortable filter showFilterMenu={false} style={{ width: '10%' }}/> */}
                <Column field="from" header="From" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="time_since" header="Hours Since" sortable dataType="numeric" filter style={{ width: '15%' }}/>
            </DataTable>
        </div>
    );
}

function Galaxy(props) {
    const [filters, setFilters] = useState({
        time: { value: null, matchMode: FilterMatchMode.CONTAINS },
        day: { value: null, matchMode: FilterMatchMode.CONTAINS },
        time_since: { value: null, matchMode: FilterMatchMode.LESS_THAN_OR_EQUAL_TO },
        from: { value: null, matchMode: FilterMatchMode.CONTAINS },
        to: { value: null, matchMode: FilterMatchMode.CONTAINS },
        news: { value: null, matchMode: FilterMatchMode.CONTAINS },
    });
    if (props.galaxynews.length === 0) {
        return null;
    }
    const news = props.galaxynews;
    const newsRowsPrime = news.map((newsItem) => {
            return {
                "time": new Date(newsItem.time).toLocaleString(),
                "day": getNiceTimeString(newsItem.time),
                "time_since": getHoursSince(newsItem.time),
                "from": (newsItem.from != "") ? props.kdNames[newsItem.from] + ' (' + props.galaxyMap[newsItem.from] + ')' : "",
                "to": (newsItem.to != "") ? props.kdNames[newsItem.to] + ' (' + props.galaxyMap[newsItem.to] + ')' : "",
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
                rows={10}
                rowsPerPageOptions={[5, 10, 25, 50]}
                sortMode="multiple"
                removableSort
                filters={filters}
                filterDisplay="row"
                style={{ width: '100%'}}
                header={"Galaxy News"}
            >
                <Column field="time" header="Time" sortable filter showFilterMenu={false} style={{ width: '15%' }}/>
                <Column field="news" header="News" filter showFilterMenu={false} style={{ width: '45%' }}/>
                {/* <Column field="day" header="Day" sortable filter showFilterMenu={false} style={{ width: '10%' }}/> */}
                <Column field="from" header="From" sortable filter showFilterMenu={false} style={{ width: '10%' }}/>
                <Column field="to" header="To" sortable filter showFilterMenu={false} style={{ width: '10%' }}/>
                <Column field="time_since" header="Hours Since" sortable dataType="numeric" filter style={{ width: '10%' }}/>
            </DataTable>
        </div>
    );
}

function Empire(props) {
    if (props.empirenews.length === 0) {
        return null;
    }
    const news = props.empirenews;
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{props.kdNames[newsItem.to]} ({props.galaxyMap[newsItem.to]})</td>
            <td>{newsItem.news}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover>
                <thead>
                    <tr>
                    <th>Time</th>
                    <th>Time Since</th>
                    <th>To</th>
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

function Universe(props) {
    if (props.universenews.length === 0) {
        return null;
    }
    const news = props.universenews;
    const newsRows = news.map((newsItem) =>
        <tr key={newsItem.time}>
            <td>{getNiceTimeString(newsItem.time)}</td>
            <td>{getTimeSinceString(newsItem.time)}</td>
            <td>{newsItem.news}</td>
        </tr>
    );
    return (
        <div className="kingdom">
            <Table striped bordered hover>
                <thead>
                    <tr>
                    <th>Time</th>
                    <th>Time Since</th>
                    <th>News</th>
                    </tr>
                </thead>
                <tbody>
                    {newsRows}
                </tbody>
            </Table>
        </div>
    );
}

export default NewsContent;