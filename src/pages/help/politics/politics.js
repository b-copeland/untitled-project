import { displayPercent } from "../../../format";
import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Politics(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "politics") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="politics" ref={yourElementRef} className="help-section">
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
            <p>
                Once you change a vote (the leader, or either doctrine), it stays for
                {" "}{(props.state.game_config?.BASE_GALAXY_VOTE_COOLDOWN_EPOCHS * props.state.game_config?.BASE_EPOCH_SECONDS / 3600) || "a few"} hours,
                and the page says when you can change it again. Your first vote, and voting for what you already vote for,
                start no wait.
            </p>
        </div>
    )
}

export default Politics;