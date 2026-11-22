import React from "react";
import { Link, useNavigate } from "react-router-dom";
import Dropdown from "react-bootstrap/Dropdown";
import { FiUser } from "react-icons/fi";
import { logout } from "../auth";
import "./usermenu.css";

/**
 * The account button at the top right of every page for a signed-in player: their username, and a menu with Settings
 * and Logout. The username comes with the preferences (``GET /api/preferences``); until it arrives the button says
 * "Account". ``id`` keeps the desktop and phone copies apart.
 */
function UserMenu({ username, id = "user-menu" }) {
    const navigate = useNavigate();
    const onLogout = () => {
        logout();
        navigate("/login");
    };
    return (
        <Dropdown align="end" className="user-menu">
            <Dropdown.Toggle id={id} variant="outline-secondary" className="user-menu-toggle" aria-label={`Account: ${username || "you"}`}>
                <FiUser aria-hidden="true" />
                <span className="user-menu-name">{username || "Account"}</span>
            </Dropdown.Toggle>
            <Dropdown.Menu>
                {username ? <Dropdown.Header>Signed in as <strong>{username}</strong></Dropdown.Header> : null}
                <Dropdown.Item as={Link} to="/settings">Settings</Dropdown.Item>
                <Dropdown.Divider />
                <Dropdown.Item as="button" onClick={onLogout}>Logout</Dropdown.Item>
            </Dropdown.Menu>
        </Dropdown>
    );
}

export default UserMenu;
