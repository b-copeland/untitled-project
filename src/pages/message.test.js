import React from "react";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import Message from "./message";

jest.mock("../components/helpbutton", () => () => null);
jest.mock("../auth", () => ({ authFetch: jest.fn(() => Promise.resolve({ json: () => Promise.resolve({}) })) }));

const data = {
    messages: [], kingdoms: { 1: "Alpha" }, galaxies_inverted: { 1: "1:1" }, kingdomid: { kd_id: "1" },
    notifs: { messages: 2, galaxy_board: 3 },
    galaxyboard: { galaxy: "1:1", posts: [{ id: "a", time: new Date().toISOString(), from: "1", text: "Board post" }] },
    state: { game_config: { GALAXY_BOARD_MAX_LENGTH: 500 } },
};
const show = (path) => render(
    <MemoryRouter initialEntries={[path]}><Message data={data} loading={{}} updateData={jest.fn()} /></MemoryRouter>);

test("the page has a tab for messages and one for the galaxy board, each with its unread count", () => {
    show("/message");
    expect(screen.getByRole("tab", { name: "Messages (2)" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Galaxy Board (3)" })).toBeTruthy();
    expect(screen.queryByText("Board post")).toBeNull();  // the board loads when its tab opens
});

test("?tab=board opens the galaxy board", () => {
    show("/message?tab=board");
    expect(screen.getByText("Board post")).toBeTruthy();
});
