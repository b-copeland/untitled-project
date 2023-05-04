import React, { useMemo, useEffect, useState } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Galaxy(props) {
    return (
        <div id="galaxy" className="help-section">
            <h2>Galaxy</h2>
            <p>
                The galaxy page allows you to view the different galaxies in the universe. 
            </p>
            <p>
                You can not view the stats (stars or networth) for kingdoms in foreign galaxies 
                unless they have first been revealed. Certain aggressive actions will cause kingdoms to be revealed, 
                such as attacking a kingdom in your galaxy or having a spy attempt caught on spy radar.
            </p>
            <p>
                When kingdoms have stats revealed, you can press the "View" button to see information about that kingdom. Additionally, 
                there are various buttons to interact with each kingdom.
            </p>
            <p>
                When viewing your own galaxy, you can press the "Share" button to share your kingdom's details with a galaxymate. 
                You should only use this with galaxymates you trust, since they will be able to view virtually any information about 
                your kingdom at any time. You can choose to unshare your information at a later time. 
            </p>
        </div>
    )
}

export default Galaxy;