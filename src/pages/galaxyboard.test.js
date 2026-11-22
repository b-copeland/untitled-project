import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import GalaxyBoard from "./galaxyboard";
import { checkPost } from "../validation";

jest.mock("../components/helpbutton", () => () => null);
jest.mock("../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) })) }));

const time = new Date().toISOString();
const data = (board = {}) => ({
    galaxyboard: {
        galaxy: "1:1", can_moderate: false, pinned: null,
        posts: [
            { id: "b", time, from: "2", text: "Join us: https://discord.gg/abc" },
            { id: "a", time, from: "1", text: "Mine" },
        ],
        ...board,
    },
    kingdoms: { 1: "Alpha", 2: "Bravo" },
    kingdomid: { kd_id: "1" },
    state: { game_config: { GALAXY_BOARD_MAX_LENGTH: 10 } },
});

let updateData;
beforeEach(() => {
    updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    require("../auth").authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const show = (d) => render(<MemoryRouter><GalaxyBoard data={d} loading={{}} updateData={updateData} /></MemoryRouter>);

test("posts show their author, and web addresses are links that open in a new tab", () => {
    show(data());
    expect(screen.getByText("Bravo")).toBeTruthy();
    const link = screen.getByRole("link", { name: "https://discord.gg/abc" });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
});

test("a player can delete only their own posts; the leader can delete and pin any", () => {
    const { unmount } = show(data());
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Pin to the top" })).toBeNull();
    unmount();
    show(data({ can_moderate: true }));
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: "Pin to the top" })).toHaveLength(2);
});

test("the post button says why it is blocked, and sends the text", () => {
    show(data());
    const button = screen.getByRole("button", { name: "Post" });
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Post"), { target: { value: "x".repeat(11) } });
    expect(button.getAttribute("title")).toBe("At most 10 characters");
    fireEvent.change(screen.getByLabelText("Post"), { target: { value: "hi all" } });
    fireEvent.click(button);
    const { authFetch } = require("../auth");
    expect(authFetch).toHaveBeenCalledWith("api/galaxyboard", { method: "POST", body: JSON.stringify({ text: "hi all" }) });
});

test("a pinned post shows in its own panel", () => {
    show(data({ pinned: { id: "b", time, from: "2", text: "Pinned words" } }));
    expect(screen.getByText("Pinned")).toBeTruthy();
    expect(screen.getByText("Pinned words")).toBeTruthy();
});

test("checkPost counts the trimmed text", () => {
    expect(checkPost("   ", 10)).toBe("Write something to post");
    expect(checkPost("  12345  ", 5)).toBeNull();
    expect(checkPost("123456", 5)).toBe("At most 5 characters");
});
