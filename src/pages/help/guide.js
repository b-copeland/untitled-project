import React, { useMemo, useEffect, useState, useRef } from "react";
import 'bootstrap/dist/css/bootstrap.css';

function Guide(props) {
    const yourElementRef = useRef(null);
  
    useEffect(() => {
      if (Object.keys(props.state).length > 0 && props.scrollTarget === "guide") {
        yourElementRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [props.state]);
    return (
        <div id="guide" ref={yourElementRef} className="help-section">
            <h2>Guide</h2>
            <p>
                Welcome to Untitled Space Game. You are the ruler of an interstellar kingdom. 
                The goal of the game is to have the most points at the end of the round (or to have fun). 
                You gain points while your kingdom is one of the strongest kingdoms in the universe. 
                If you lose all of your stars or your population hits 0 at any point during the round, your kingdom 
                is dead for the remainder of the round, but you keep any points you've accumulated.
            </p>
            <p>
                Your kingdom is part of a galaxy. You will likely want to work together with your galaxy to grow your kingdom 
                and protect yourself against other galaxies. As a galaxy, you might benefit from sharing information and strategies, 
                and sometimes even coordinating attacks and spy attempts to become stronger than kingdoms in other galaxies.
            </p>
            <p>
                In order for your kingdom to get stronger, you should generally always be growing your kingdom. The first step to 
                growing is to gain more stars. You can gain more stars by Settling, attacking Primitives, or attacking other players.
            </p>
            <p>
                After gaining stars, you will want to build new Structures to increase your production. You can 
                build one structure for each star that you own. Structures provide various benefits, such as increasing 
                your income, increasing your population, making and storing fuel, or storing your military. As long as it is 
                safe to do so, you should prioritize building structures on your available stars as soon as possible to maximize 
                your income.
            </p>
            <p>
                You will build military to protect your kingdom or to be able to attack other kingdoms. Some units provide offense, 
                some units provide defense, and some units provide both. If another kingdom attacks you by sending offensive units 
                with more strength than your kingdom's defensive units, they will defeat you in battle and take some of your stars. 
                Additionally, being attacked causes you to lose a portion of your kingdom's defensive units.
            </p>
            <p>
                However, if an attacking kingdom does not have enough offensive units to overpower your defense, their attack will
                only cause you to lose some defensive units, and you will not lose any stars. This makes it important to prioritize 
                keeping your defensive strength higher than other players' offensive strength. But once you know you are safe, training 
                your own offensive units may allow you to successfully attack other smaller players.
            </p>
            <p>
                Most aspects of your kingdom can be improved through Projects. Your engineers can be assigned to projects which will provide 
                some ongoing benefit or a one-time benefit, such as unlocking a new military unit. You should generally aim to have your 
                Continuous projects at their max bonus, so that your kingdom is growing as quickly as possible. However, as you gain more 
                stars, Continuous projects will become exponentially more difficult to maintain, so you may have to prioritize bonuses 
                that are most important to you.
            </p>
            <p>
                Your kingdom's drones are able to perform spy operations to gather intel or to hinder other kingdoms. You will need to rely 
                on this intel to be able to successfully attack other kingdoms, especially military intel. When you successfully spy on a 
                kingdom, you will gain access to a part of that kingdom's information for a period of time. In the case of military intel, 
                you will be able to see how many units an enemy kingdom has, so that you can calculate how many units you need to send to 
                defeat them in battle.
            </p>
            <p>
                The more drones that you have, the less susceptible your kingdom will be to spy operations from other kingdoms. So you'll want to 
                invest some of your structures into Drone Factories to ensure that your kingdom is not an easy target for spy operations.
            </p>
            <p>
                There are various levels of Politics that affect your kingdom. You'll want to work together with your galaxy to vote 
                on policies which are best suited for your galaxy's growth.
            </p>
            <p>
                Your kingdom can expend Fuel to power Shields. Shields provide benefits such as improving your military defense, making spy attempts 
                against you less likely to succeed, or preventing Missile damage to your kingdom. It's a good idea to keep at least your military shields maxed 
                if you have enough fuel to do so.
            </p>
            <p>
                If you run out of fuel, your kingdom's population growth and military strength will be greatly reduced, and your shields will be powered off. 
                You should always try to keep a buffer of fuel to ensure that your kingdom does not suddenly become fuelless.
            </p>
            <p>
                You can enable Auto Spending to have your kingdom's Build operations managed for you. When you enable auto spending, you will choose percentages 
                for the various spending categories. Your income will then go into funding for those specific categories at the rates you chosen, where it will 
                be used to automatically Settle, build Structures, train Military, or train Engineers. The general priority for spending should be 
                Military {'>'} Structures {'>'} Settle {'>'} Engineers.
            </p>
            <p>
                Note that for Structures and Military, simply enabling auto spending is not enough to automatically build these resources. You will need to go 
                into the Allocate tab on these pages to choose the allocation of structures/units that you would like the auto-spender to build towards.
            </p>
        </div>
    )
}

export default Guide;