import React from "react";
import { Topic, config, duration } from "../util";

function Spending(props) {
    const cfg = config(props.state);
    return (
        <Topic id="spending" title="Auto spending" lead="Let your income build your kingdom for you.">
            <p>
                On the Spending tab of the Automation page, give each category a share of your income: settling,
                structures, military and engineers. The shares add up to at most 100%. Whatever is left stays as money
                you spend yourself. Press Update to save.
            </p>
            <p>
                While auto spending is on, each share of the money you make (income, attacks and robs) goes into that
                category's funding. About every {duration(cfg.BASE_AUTO_SPENDING_TIME_MULTIPLIER, cfg)} the game spends
                each category's funding as far as it can. The Build page shows how much funding each category holds.
            </p>
            <p>
                <b>Structures and military need targets.</b> Without a target mix (Structure targets and Unit targets
                on the Automation page), their funding builds up and is never spent.
            </p>
            <p>
                <b>Moving funding.</b> Under Funding set aside, choose where to move from, where to, and how much: take
                funding back as money, move it from one category to another, or put money into a category for the auto
                spender to spend at its next run. Money can only go into a category while auto spending is on. Nothing
                is lost: money and funding count the same towards networth and are taken alike by attacks.
            </p>
            <p>Turning auto spending off returns all funding to your money.</p>
        </Topic>
    );
}

export default Spending;
