import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function EmpirePolitics(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="empirepolitics" className="help-section">
            <h2>Politics - Empire</h2>
            <p>
                Empire politics are not currently enabled. Eventually this page will 
                allow galaxy leaders to create/join an empire.
            </p>
        </div>
    )
}

export default EmpirePolitics;