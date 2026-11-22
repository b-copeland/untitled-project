import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import UserMenu from "./usermenu";
import { logout } from "../auth";

jest.mock("../auth", () => ({ logout: jest.fn() }));

const renderMenu = (username) => render(<MemoryRouter><UserMenu username={username} /></MemoryRouter>);

test("the button shows the username, and the menu has Settings and Logout", async () => {
    renderMenu("user1");
    fireEvent.click(screen.getByRole("button", { name: "Account: user1" }));
    expect(await screen.findByText("Signed in as")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Account: user1" })).toHaveTextContent("user1");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    fireEvent.click(screen.getByRole("button", { name: "Logout" }));
    expect(logout).toHaveBeenCalled();
});

test("before the username arrives the button says Account", () => {
    renderMenu(undefined);
    expect(screen.getByRole("button", { name: "Account: you" })).toHaveTextContent("Account");
});
