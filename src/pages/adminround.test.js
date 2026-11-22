import {render, screen, fireEvent, waitFor} from "@testing-library/react";
import AdminRound, {newRoundErrors, toInput, fromInput} from "./adminround";
import {adminAuth} from "../auth";

jest.mock("../auth", () => ({adminAuth: {authFetch: jest.fn()}}));

const round = {
    phase: "running", game_start: "2026-11-20T10:00:00+00:00", game_end: "2026-11-27T10:00:00+00:00",
    election_start: "2026-11-22T10:00:00+00:00", election_end: "", game_over: "", rounds_archived: 2,
    cluster_size: 5, galaxies: 10, clusters: 2, kingdoms: 30, bots: 20, players: 10,
    default_cluster_size: 5, max_galaxies: 100, max_bots: 200, election_hours: 24, election_every_hours: 168,
};

const respond = (body) => Promise.resolve({json: () => Promise.resolve(body)});

beforeEach(() => {
    adminAuth.authFetch.mockImplementation((url, options) => {
        if (url === "api/admin/round" && !options) return respond(round);
        if (url === "api/admin/newround") return respond({status: "success", message: "New round ready", round});
        if (url === "api/admin/bots") return respond({status: "success", message: "Created 12 bots"});
        return respond({status: "success", message: "ok"});
    });
});

const future = (hours) => new Date(Date.now() + hours * 3600 * 1000);
const good = () => ({start: toInput(future(2)), end: toInput(future(24 * 7)), election: toInput(future(48)),
                     noElections: false, galaxies: "10", clusterSize: "5", bots: "0"});

test("a datetime-local value goes to the server as UTC and back", () => {
    const date = new Date(2030, 0, 2, 15, 30);
    expect(toInput(date)).toBe("2030-01-02T15:30");
    expect(fromInput("2030-01-02T15:30")).toBe(date.toISOString());
    expect(fromInput("")).toBe("");
});

test("a good new round has no errors", () => {
    expect(newRoundErrors(good())).toEqual({});
    expect(newRoundErrors({...good(), noElections: true, election: ""})).toEqual({});
});

test("a bad new round says which field is wrong", () => {
    expect(newRoundErrors({...good(), end: toInput(future(1))})).toHaveProperty("game_end");  // before the start
    expect(newRoundErrors({...good(), end: toInput(future(-1)), start: toInput(future(-5))})).toHaveProperty("game_end");
    expect(newRoundErrors({...good(), election: toInput(future(24 * 30))})).toHaveProperty("election_start");
    expect(newRoundErrors({...good(), galaxies: "0"})).toHaveProperty("num_galaxies");
    expect(newRoundErrors({...good(), galaxies: "101"})).toHaveProperty("num_galaxies");
    expect(newRoundErrors({...good(), clusterSize: "0"})).toHaveProperty("cluster_size");
    expect(newRoundErrors({...good(), start: ""})).toHaveProperty("game_start");
});

test("shows where the round stands", async () => {
    render(<AdminRound/>);
    await waitFor(() => screen.getByText("Running"));
    expect(screen.getByText("10 in 2 clusters")).toBeTruthy();
    expect(screen.getByText("Change the dates")).toBeTruthy();
    expect(screen.getByText("End the round now")).toBeTruthy();
});

test("starting a round asks first, then sends the round and adds the bots", async () => {
    render(<AdminRound/>);
    await waitFor(() => screen.getByText("Start new round"));
    fireEvent.change(document.getElementById("newround-bots"), {target: {value: "12"}});
    fireEvent.click(screen.getByText("Start new round"));
    await waitFor(() => screen.getByText("Start a new round?"));
    expect(screen.getByText(/then 12 bots/)).toBeTruthy();

    fireEvent.click(screen.getByText("Delete it and start"));

    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/bots", expect.anything()));
    const [, newRound] = adminAuth.authFetch.mock.calls.find(([url]) => url === "api/admin/newround");
    const body = JSON.parse(newRound.body);
    expect(body).toMatchObject({num_galaxies: 10, cluster_size: 5, archive: true});
    expect(new Date(body.game_end) - new Date(body.game_start)).toBe(7 * 24 * 3600 * 1000);
    const [, bots] = adminAuth.authFetch.mock.calls.find(([url]) => url === "api/admin/bots");
    expect(JSON.parse(bots.body)).toEqual({total: 12});
});

test("a refused new round adds no bots and shows the server's reason under the field", async () => {
    adminAuth.authFetch.mockImplementation((url, options) => {
        if (url === "api/admin/round" && !options) return respond(round);
        if (url === "api/admin/newround") return respond({message: "Between 1 and 100 galaxies", errors: {num_galaxies: "Between 1 and 100 galaxies"}});
        return respond({status: "success"});
    });
    render(<AdminRound/>);
    await waitFor(() => screen.getByText("Start new round"));
    fireEvent.change(document.getElementById("newround-bots"), {target: {value: "3"}});
    fireEvent.click(screen.getByText("Start new round"));
    fireEvent.click(await screen.findByText("Delete it and start"));

    await waitFor(() => expect(screen.getAllByText("Between 1 and 100 galaxies").length).toBeGreaterThan(0));
    expect(adminAuth.authFetch.mock.calls.some(([url]) => url === "api/admin/bots")).toBe(false);
});

test("a game with no round offers only the new round", async () => {
    adminAuth.authFetch.mockImplementation(() => respond({...round, phase: "not set up", game_start: "", game_end: "", galaxies: 0, clusters: 0}));
    render(<AdminRound/>);
    await waitFor(() => screen.getByText("No round is set up yet"));
    expect(screen.queryByText("Change the dates")).toBeNull();
    expect(screen.queryByText("Add bots")).toBeNull();
    expect(screen.getByText("Start new round")).toBeTruthy();
});
