import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function History(props) {
    return (
        <div id="history" className="help-section">
            <h2>History</h2>
            <p>
                The history page shows actions that you have taken against other kingdoms. 
                You can sort or filter the columns in the header.
            </p>
            <p>
                The stats page will show historical details of your kingdom, such stars or networth across time. 
                Not yet implemented.
            </p>
        </div>
    )
}

export default History;