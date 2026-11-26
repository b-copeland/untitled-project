import React from "react";

/*
 * The forecast tables of the Status page and another kingdom's Production tab: a column for now, then one per forecast
 * horizon (``QUEUE_FORECAST_EPOCHS``), each showing now plus what the queue adds by then (``future_<epochs>`` from the
 * API).
 */

/** A column heading for a forecast that many epochs ahead, in real time: "30m", "1h", "24h". */
export function horizonLabel(epochs, cfg) {
    const seconds = (epochs || 0) * (cfg?.BASE_EPOCH_SECONDS || 0);
    if (seconds > 0 && seconds < 3600) {
        return `${Math.round(seconds / 60)}m`;
    }
    return `${Math.round((seconds / 3600) * 10) / 10}h`;
}

export function ForecastHead({ horizons, cfg }) {
    return (
        <thead>
            <tr>
                <th style={{textAlign: "right"}}></th>
                <th style={{textAlign: "right"}}>Now</th>
                {horizons.map((epochs) => <th key={epochs} style={{textAlign: "right"}}>{horizonLabel(epochs, cfg)}</th>)}
            </tr>
        </thead>
    );
}

export const wholeNumber = (value) => Math.floor(value || 0).toLocaleString();

/** One row: the amount now, then now plus what the queue adds by each horizon (``future_<epochs>`` from the API). */
export function ForecastRow({ label, now, horizons, at, show = wholeNumber }) {
    return (
        <tr>
            <td style={{textAlign: "left"}}>{label}</td>
            <td style={{textAlign: "right"}}>{show(now || 0)}</td>
            {horizons.map((epochs) => (
                <td key={epochs} style={{textAlign: "right"}}>{show((now || 0) + (at(`future_${epochs}`) || 0))}</td>
            ))}
        </tr>
    );
}

/** The heading for what a queue delivers: one column per horizon ("within 1h"), then everything in the queue. */
export function ArrivalsHead({ horizons, cfg }) {
    return (
        <thead>
            <tr>
                <th style={{textAlign: "right"}}></th>
                {horizons.map((epochs) => <th key={epochs} style={{textAlign: "right"}}>{`Within ${horizonLabel(epochs, cfg)}`}</th>)}
                <th style={{textAlign: "right"}}>All queued</th>
            </tr>
        </thead>
    );
}

/** One row of ArrivalsHead's columns: what lands by each horizon (``future_<epochs>``), then ``queued``. */
export function ArrivalsRow({ label, horizons, at, show = wholeNumber }) {
    return (
        <tr>
            <td style={{textAlign: "left"}}>{label}</td>
            {horizons.map((epochs) => <td key={epochs} style={{textAlign: "right"}}>{show(at(`future_${epochs}`) || 0)}</td>)}
            <td style={{textAlign: "right"}}>{show(at("queued") || 0)}</td>
        </tr>
    );
}
