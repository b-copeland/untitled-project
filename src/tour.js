/*
 * The guided tour's stops, in order (the machinery is components/tour.js). Each stop is a page (`path`), a title and a
 * few sentences, and optionally `target`: the `data-tour` name of the element to highlight on that page
 * (`<Panel data-tour="shields-panel">`, or on a `<Tabs>`, which puts it on the tab bar). A target that is not on the
 * page (still loading, or not there for this kingdom) is simply not highlighted. tour.test.js checks every target is
 * named somewhere in src/.
 *
 * `path` and `text` may be functions of the tour's context: `{ demo, demoName }`, the kingdom the Attack and Spy stops
 * use as an example (from another galaxy, chosen when the tour starts), or undefined when there is none.
 *
 * Keep the words plain and in the game's terms (docs/game-design.md#glossary), and no game numbers: the stops explain
 * where things are, and the help topics hold the rules.
 */

/** Seconds a stop takes to read, for "about N minutes". */
export const SECONDS_PER_STOP = 15;

const withTarget = (path, demo, extra = "") => (demo ? `${path}?target=${demo}${extra}` : path);
const example = (demoName) => (demoName ? `${demoName} is filled in as an example` : "Choose a kingdom here");

export const TOUR_STOPS = [
    {
        path: "/status", title: "Welcome to your kingdom",
        text: "The Status page is your kingdom at a glance: what changed since your last visit, your economy, "
            + "military, growth and threats. Each card's title opens the page where you act on it. Nothing is sent "
            + "or spent during the tour.",
    },
    {
        path: "/status", target: "status-advisors", title: "Advisors",
        text: "Your advisors point out what in your kingdom may need fixing, with a link to the page that fixes it. "
            + "Check here first each time you come back.",
    },
    {
        path: "/status", target: "status-tabs", title: "More detail",
        text: "The Kingdom, Military and Structures tabs have the full numbers: every resource and what it earns, "
            + "every unit you have and are training, and every structure built and being built.",
    },
    {
        path: "/shields", target: "shields-panel", title: "Shields",
        text: "Shields burn fuel every hour to protect you. Military shields add to your defense, and matter most: "
            + "keep them as high as you can afford. The others work against spies and missiles.",
    },
    {
        path: "/shields", target: "shields-fuel", title: "Fuel",
        text: "Watch your fuel. Without it your population stops growing, your army gets much weaker and your "
            + "shields switch off. Fuel plants make it.",
    },
    {
        path: "/galaxy", target: "galaxy-kingdoms", title: "Your galaxy",
        text: "Your galaxy is your team. These are your galaxymates: you share intel, plan attacks together and vote "
            + "together.",
    },
    {
        path: "/galaxy", target: "galaxy-nav", title: "Other galaxies",
        text: "Use the arrows, or type a cluster and galaxy number, to look at other galaxies. That is where you find "
            + "kingdoms to attack, and see who could attack you.",
    },
    {
        path: "/galaxy", target: "galaxy-actions", title: "Acting on a kingdom",
        text: "The buttons beside each kingdom act on it: view it, attack, spy, launch missiles, send a message, "
            + "pin it to your Conquer page, and share your own kingdom with a galaxymate.",
    },
    {
        path: "/automation", target: "automation-items", title: "Automation",
        text: "Your kingdom can run itself while you are away, and this is where you set that up. This list shows "
            + "everything automatic, whether it is on, and what it will do. Each one has a tab with its settings.",
    },
    {
        path: "/automation?tab=spending", target: "automation-tabs", title: "Auto spending",
        text: "Auto spending puts your income into settling, structures, military and engineers, in the shares you "
            + "set here. Turn it on so your kingdom keeps growing between your visits.",
    },
    {
        path: "/automation?tab=structures", target: "automation-tabs", title: "Structure targets",
        text: "Tell auto spending what to build: the share of your stars for each structure. Without targets it has "
            + "nothing to build.",
    },
    {
        path: "/automation?tab=units", target: "automation-tabs", title: "Unit targets",
        text: "The same for your military: the mix of units auto spending trains.",
    },
    {
        path: "/automation?tab=projects", target: "automation-tabs", title: "Project targets",
        text: "Projects give bonuses and unlock new units. Pick the projects your new engineers work on.",
    },
    {
        path: "/automation?tab=primitives", target: "automation-tabs", title: "Primitives, automatically",
        text: "Attacking and robbing primitives can run on their own: set the share of units or drones to send, then "
            + "switch them on.",
    },
    {
        path: "/automation?tab=schedule", target: "automation-tabs", title: "Schedule",
        text: "Queue an attack, a spy operation or missiles for a set time while you are away. The Schedule page "
            + "also repeats operations, and reacts when you are attacked, spied on, hit by missiles or low on fuel.",
    },
    {
        path: "/build", target: "build-queues", title: "Build",
        text: "The Build pages in the menu are where you spend by hand: settle stars, build structures, train "
            + "military, put engineers on projects and build missiles. This one shows what is on its way and when.",
    },
    {
        path: "/conquer", target: "conquer-tabs", title: "Conquer",
        text: "Every kingdom you have intel on is listed here, with what you know and for how long. Pin a kingdom "
            + "(from the Galaxy page or its own page) to keep it on the Pinned tab.",
    },
    {
        path: ({ demo }) => withTarget("/attack", demo), target: "attack-target", title: "Attack: the target",
        text: ({ demoName }) => `An attack starts with a target. ${example(demoName)}. What you have revealed about `
            + "them shows here.",
    },
    {
        path: ({ demo }) => withTarget("/attack", demo), target: "attack-defense", title: "Attack: their defense",
        text: "What their army is worth. Without intel these numbers are guesses, marked Estimate needed: spy on their "
            + "military to see the real ones.",
    },
    {
        path: ({ demo }) => withTarget("/attack", demo), target: "attack-units", title: "Attack: your army",
        text: "Choose the units and generals to send. A suggestion is filled in for you. The more you send, the less "
            + "is left at home to defend you.",
    },
    {
        path: ({ demo }) => withTarget("/attack", demo), target: "attack-forecast", title: "Attack: forecast and send",
        text: "Before you send, the forecast shows your offense against their defense, whether the attack should "
            + "succeed, and the units each side would lose. Send attack is off while the tour runs: "
            + "spy on a kingdom before you attack it.",
    },
    {
        path: ({ demo }) => withTarget("/spy", demo, "&op=spymilitary"), target: "spy-target", title: "Spy",
        text: "Spying uses drones and spy attempts. Spy on military shows their army exactly, and comes before almost "
            + "every attack: an attack on guesses is a gamble.",
    },
    {
        path: ({ demo }) => withTarget("/spy", demo, "&op=spymilitary"), target: "spy-forecast", title: "Spy: forecast and send",
        text: "The forecast shows your chance of success and the drones you would lose. Send spies is off while the tour "
            + "runs.",
    },
    {
        path: "/intel", target: "intel-tabs", title: "Intel",
        text: "Your galaxy's intel market. Share what you revealed with your galaxymates, free or for a cut of the "
            + "spoils from attacks on that kingdom, take what they have revealed, or post a bounty for intel you want.",
    },
    {
        path: "/primitives", target: "primitives-tabs", title: "Primitives",
        text: "Primitives are unclaimed land held by nobody. Attack them with your military to gain stars, or rob "
            + "them with drones to gain money. No player is on the other side.",
    },
    {
        path: "/galaxypolitics", title: "Politics",
        text: "Your galaxy votes for a leader and policies, galaxies join into empires that go to war, and the "
            + "universe votes on policies for everyone. Come back once you have settled in. That is the tour: every "
            + "page has a Help button, and Settings can start the tour again.",
    },
];

/** "about 6 minutes" for the whole tour. */
export function tourLength(stops = TOUR_STOPS) {
    const minutes = Math.max(1, Math.round((stops.length * SECONDS_PER_STOP) / 60));
    return `about ${minutes} minute${minutes === 1 ? "" : "s"}`;
}

/**
 * The example kingdom for the Attack and Spy stops: the lowest-numbered kingdom outside the player's galaxy, or
 * undefined if there is none. From data the app already has, so it costs no request.
 */
export function demoTarget(data) {
    const inverted = data.galaxies_inverted || {};
    const own = data.kingdomid?.kd_id;
    const ownGalaxy = inverted[own];
    return Object.keys(data.kingdoms || {})
        .filter((kdId) => kdId !== String(own) && inverted[kdId] && inverted[kdId] !== ownGalaxy)
        .sort((a, b) => Number(a) - Number(b))[0];
}

/** A stop's `path` or `text`, worked out for this tour. */
export const resolve = (value, context) => (typeof value === "function" ? value(context) : value);
