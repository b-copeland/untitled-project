import {render, screen, fireEvent, waitFor} from "@testing-library/react";
import AdminAccounts, {filterAccounts, sharedBy} from "./adminaccounts";
import {adminAuth} from "../auth";

jest.mock("../auth", () => ({adminAuth: {authFetch: jest.fn()}}));

const row = (overrides) => ({
    id: 1, username: "ann", roles: ["operator"], admin: false, bot: false, kd_id: "", kingdom: "", email: "",
    email_verified: false, banned: false, banned_at: "", ban_reason: "", last_login: "", addresses: 0, devices: 0,
    shares: [], ...overrides,
});
const accounts = [
    row({id: 1, username: "ann", kingdom: "Annland", kd_id: "4", shares: [{id: 2, username: "bob", ip: true, device: true}]}),
    row({id: 2, username: "bob", banned: true, ban_reason: "Multi-accounting", shares: [{id: 1, username: "ann", ip: true, device: true}]}),
    row({id: 3, username: "bot_thief_1", bot: true}),
    row({id: 4, username: "admin", admin: true}),
];

beforeEach(() => {
    adminAuth.authFetch.mockImplementation((url, options) => Promise.resolve({
        json: () => Promise.resolve(options ? {message: "Done", status: "success"} : {accounts, seen_days: 90}),
    }));
});

test("says what two accounts share", () => {
    expect(sharedBy({ip: true, device: false})).toBe("address");
    expect(sharedBy({ip: true, device: true})).toBe("address and device");
});

test("filters by text, bots, sharing and bans", () => {
    expect(filterAccounts(accounts, {}).map(a => a.username)).toEqual(["ann", "bob", "admin"]);
    expect(filterAccounts(accounts, {bots: true}).length).toBe(4);
    expect(filterAccounts(accounts, {text: "annl"}).map(a => a.username)).toEqual(["ann"]);
    expect(filterAccounts(accounts, {sharedOnly: true}).map(a => a.username)).toEqual(["ann", "bob"]);
    expect(filterAccounts(accounts, {bannedOnly: true}).map(a => a.username)).toEqual(["bob"]);
});

test("lists accounts with who they share with, and bans one with a reason", async () => {
    render(<AdminAccounts/>);
    await waitFor(() => screen.getByText("Annland"));
    expect(screen.queryByText(/bot_thief_1/)).toBeNull();
    expect(screen.getAllByText("(address and device)").length).toBe(2);

    fireEvent.click(screen.getAllByRole("button", {name: "ann"})[0]);
    fireEvent.change(screen.getByPlaceholderText(/Reason/), {target: {value: "Two accounts"}});
    fireEvent.click(screen.getByRole("button", {name: "Ban"}));

    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/accounts/1/ban",
        {method: "POST", body: JSON.stringify({reason: "Two accounts"})}));
});

test("sets a password, and a banned account can be unbanned", async () => {
    render(<AdminAccounts/>);
    await waitFor(() => screen.getByText("Annland"));
    fireEvent.click(screen.getAllByRole("button", {name: "bob"})[0]);
    fireEvent.change(screen.getByLabelText("New password"), {target: {value: "fresh"}});
    fireEvent.click(screen.getByRole("button", {name: "Set"}));
    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/accounts/2/password",
        {method: "POST", body: JSON.stringify({password: "fresh"})}));

    fireEvent.click(screen.getByRole("button", {name: "Unban"}));
    await waitFor(() => expect(adminAuth.authFetch).toHaveBeenCalledWith("api/admin/accounts/2/unban",
        {method: "POST", body: undefined}));
});

test("an admin account has no ban button", async () => {
    render(<AdminAccounts/>);
    await waitFor(() => screen.getByText("Annland"));
    fireEvent.click(screen.getByRole("button", {name: "admin (admin)"}));
    expect(screen.getByText(/can not be banned here/)).toBeTruthy();
    expect(screen.queryByRole("button", {name: "Ban"})).toBeNull();
});
