import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function News(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "news") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="news" ref={yourElementRef} className="help-section">
            <h2>News</h2>
            <h4>News - Kingdom</h4>
            <p>
                The kingdom page displays news from actions taken against your kingdom. 
                You can sort news by the Time, From, or Hours Since columns, as well as filter 
                by typing in the boxes below the column headers.
            </p>
            <h4>News - Galaxy</h4>
            <p>
                The galaxy page displays news from actions involving kingdoms in your galaxy. 
                You can sort news by the Time, From, To, or Hours Since columns, as well as filter 
                by typing in the boxes below the column headers.
            </p>
            <h4>News - Empires</h4>
            <p>
                The empires page displays news from actions involving your empire. 
                Not yet implemented.
            </p>
            <h4>News - Universe</h4>
            <p>
                The universe page displays news from actions affecting the universe. 
                Not yet implemented.
            </p>
        </div>
    )
}

export default News;