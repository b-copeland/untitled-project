import {render, screen, fireEvent, waitFor} from "@testing-library/react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import {ForgotAccount, ResetPassword, VerifyEmail} from "./recovery";

const respondWith = (body) => {
    global.fetch = jest.fn(() => Promise.resolve({json: () => Promise.resolve(body)}));
};

afterEach(() => {
    delete global.fetch;
});

test("asking for a password reset posts the address and shows the neutral answer", async () => {
    respondWith({message: "If that address belongs to an account, we have sent an email to it."});
    render(<MemoryRouter><ForgotAccount/></MemoryRouter>);

    fireEvent.change(document.getElementById("email"), {target: {value: "a@example.com"}});
    fireEvent.click(screen.getByText("Email me a password reset link"));

    await waitFor(() => screen.getByText(/we have sent an email/));
    expect(global.fetch).toHaveBeenCalledWith("api/account/forgot-password", {
        method: "POST",
        body: JSON.stringify({email: "a@example.com"}),
    });
});

test("the buttons stay disabled until an address is typed", () => {
    render(<MemoryRouter><ForgotAccount/></MemoryRouter>);
    expect(screen.getByText("Remind me of my username").closest("button").disabled).toBe(true);
});

test("choosing a new password sends the token from the link", async () => {
    respondWith({status: "success", message: "Your password has been changed"});
    render(
        <MemoryRouter initialEntries={["/resetpassword?token=abc"]}>
            <Routes><Route path="/resetpassword" element={<ResetPassword/>}/></Routes>
        </MemoryRouter>
    );

    fireEvent.change(document.getElementById("password"), {target: {value: "new-pw"}});
    fireEvent.click(screen.getByText("Change password"));

    await waitFor(() => screen.getByText("Your password has been changed"));
    expect(global.fetch).toHaveBeenCalledWith("api/account/reset-password", {
        method: "POST",
        body: JSON.stringify({token: "abc", password: "new-pw"}),
    });
});

test("opening the verification link confirms the address", async () => {
    respondWith({status: "success", message: "Your email address is confirmed"});
    render(
        <MemoryRouter initialEntries={["/verifyemail?token=xyz"]}>
            <Routes><Route path="/verifyemail" element={<VerifyEmail/>}/></Routes>
        </MemoryRouter>
    );

    await waitFor(() => screen.getByText("Your email address is confirmed"));
    expect(global.fetch).toHaveBeenCalledWith("api/account/email/verify", {
        method: "POST",
        body: JSON.stringify({token: "xyz"}),
    });
});
