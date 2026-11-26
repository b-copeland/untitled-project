import {render, screen, fireEvent, waitFor} from "@testing-library/react";
import AdminUniverse from "./adminuniverse";
import {adminAuth} from "../auth";

jest.mock("../auth", () => ({adminAuth: {authFetch: jest.fn()}}));

const universe = {
    kingdoms: [
        {kd_id: "2", name: "bot_thief_1", playstyle: "thief", galaxy: "1:2", empire: "Reds", stars: 900, networth: 50, points: 4},
        {kd_id: "1", name: "Mine", playstyle: "player", galaxy: "1:1", empire: null, stars: 300, networth: 10, points: 0},
    ],
    empires: {},
};
const kingdom = {
    kingdom: {name: "bot_thief_1", race: "Vult", status: "Active", stars: 900, units: {attack: 5}, structures: {homes: 3},
              bot: {type: "thief", phase: "mid", log: [{time: "t1", kind: "plan", why: "spend on settling"}]}},
    news: [{time: "t2", news: "Enemy drones have begun siphoning"}],
};

beforeEach(() => {
    adminAuth.authFetch.mockImplementation((url) => Promise.resolve({
        json: () => Promise.resolve(url === "api/admin/universe" ? universe : kingdom),
    }));
});

test("lists every kingdom and opens one with its bot's decisions", async () => {
    render(<AdminUniverse/>);
    await waitFor(() => screen.getByText("bot_thief_1"));
    expect(screen.getByText("Mine")).toBeTruthy();

    fireEvent.click(screen.getByText("bot_thief_1"));

    await waitFor(() => screen.getByText(/spend on settling/));
    expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/kingdom/2");
    expect(screen.getByText(/Enemy drones have begun siphoning/)).toBeTruthy();
});

test("a galaxy can be picked out", async () => {
    render(<AdminUniverse/>);
    await waitFor(() => screen.getByText("bot_thief_1"));

    fireEvent.change(screen.getByLabelText("Galaxy"), {target: {value: "1:1"}});

    expect(screen.queryByText("bot_thief_1")).toBeNull();
    expect(screen.getByText("Mine")).toBeTruthy();
});


test("the tools rename the kingdom and delete a message", async () => {
    const withTools = {...kingdom, messages: [{time: "t3", with: "1", from: true, message: "rude"}], board_posts: [],
                       stray_fields: ["junk"]};
    adminAuth.authFetch.mockImplementation((url) => Promise.resolve({
        json: () => Promise.resolve(url === "api/admin/universe" ? universe
            : url.startsWith("api/admin/kingdom/2/") ? {message: "Done", status: "success"} : withTools),
    }));
    render(<AdminUniverse/>);
    await waitFor(() => screen.getByText("bot_thief_1"));
    fireEvent.click(screen.getByText("bot_thief_1"));
    await waitFor(() => screen.getByText(/rude/));
    expect(screen.getByText(/junk/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("New name"), {target: {value: "Polite"}});
    fireEvent.click(screen.getByText("Rename"));
    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/kingdom/2/rename",
        {method: "POST", body: JSON.stringify({name: "Polite"})}));

    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/kingdom/2/messages/delete",
        {method: "POST", body: JSON.stringify({message: {time: "t3", with: "1", from: true, message: "rude"}})}));
});
