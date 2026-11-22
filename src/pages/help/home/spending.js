import React, { useEffect, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Spending(props) {
    const yourElementRef = useRef(null);

    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "spending") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="spending" ref={yourElementRef} className="help-section">
            <h2>Spending</h2>
            <p>
                The Spending tab of the Automation page turns auto-spending on or off and sets how it splits your money: one slider per category, adding up to at most 100%; what is left stays as money. Press Update to save the sliders. With auto-spending enabled, 
                the game automatically spends your money to build your kingdom.
            </p>
            <p>
                When auto-spending is enabled, money from your income, attacks, or robs is allocated to funding in the percentages you've chosen. 
                You can view your current funding by category on the "Build" page.
            </p>
            <p>
                Every {(props.state.game_config?.BASE_AUTO_SPENDING_TIME_MULTIPLIER || 0) * (props.state.game_config?.BASE_EPOCH_SECONDS || 0)} seconds 
                the game engine will spend any available funding to the extent that it is able. In order for the auto-spender to build structures or units, their respective allocations
                must first be set in the "Allocate" tab of the "Structures" and "Military" pages, or on the Automation page.
            </p>
            <p>
                When auto-spending is disabled, all reserved funding is released back into money to be spent as you wish.
            </p>
        </div>
    )
}

export default Spending;
