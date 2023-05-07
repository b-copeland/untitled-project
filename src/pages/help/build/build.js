import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Build(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "build") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="build" ref={yourElementRef} className="help-section">
            <h2>Build</h2>
            <p>
                The build page displays the items in the production queue that are closest to being completed. 
                In the parenthesis next to each section title, you can see the total number of items in your queue.
            </p>
        </div>
    )
}

export default Build;