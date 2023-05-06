import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Politics(props) {
    const displayPercent = (percent) => `${(percent * 100).toFixed(1)}%`;
    return (
        <div id="politics" className="help-section">
            <h2>Politics - Galaxy</h2>
            <p>
                The Politics page allows you to interact with your galaxy's politics. The 
                Galaxy Leader vote currently does nothing.
            </p>
            <p>
                The Policies tab allows you to vote with your galaxy on difference policies across 
                doctrines. You can only vote for one policy within each doctrine. The active policy will 
                change when it has more votes than the other policy in the doctrine.
            </p>
        </div>
    )
}

export default Politics;