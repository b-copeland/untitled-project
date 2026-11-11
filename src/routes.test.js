import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { sections, publicRoutes, createKingdomRoute, gamePages, propsFor } from "./routes";
import SideNavbar from "./components/navbar";

test("no two pages share a path, and every page has a component", () => {
    const paths = [...publicRoutes, createKingdomRoute, ...gamePages].map((route) => route.path);
    expect(new Set(paths).size).toBe(paths.length);
    [...publicRoutes, createKingdomRoute, ...gamePages].forEach((route) => expect(route.component).toBeTruthy());
});

test("paths are lower case, so the links in the navigation and the routes agree", () => {
    [...publicRoutes, createKingdomRoute, ...gamePages].forEach((route) => expect(route.path).toBe(route.path.toLowerCase()));
});

test("every section opens on one of its own pages", () => {
    sections.forEach((section) => expect(section.pages.map((page) => page.path)).toContain(section.path));
});

test("a game page gets the shared props, and the extra ones it asked for", () => {
    const context = {
        data: { galaxies_inverted: { "7": "1:3" }, kingdomid: { kd_id: "7" } }, loading: false, updateData: () => {},
    };
    const galaxy = gamePages.find((page) => page.path === "/galaxy");

    expect(propsFor(galaxy, context)).toEqual({ data: context.data, loading: false, updateData: context.updateData, initialGalaxyId: "1:3" });
    expect(Object.keys(propsFor(gamePages.find((page) => page.path === "/spy"), context)).sort()).toEqual(["data", "loading", "updateData"]);
});

const renderNav = (path, notifs = {}) => render(
    <MemoryRouter initialEntries={[path]}>
        <SideNavbar logged={true} showNav={true} setShowNav={() => {}} notifs={notifs}/>
    </MemoryRouter>
);

test("the navigation lists a section's pages only while you are in that section", () => {
    renderNav("/settle");

    expect(screen.getByText(/Structures/)).toBeTruthy();
    expect(screen.queryByText(/Launch Missiles/)).toBeNull();
    ["Home", "Build", "Conquer", "Politics", "Help"].forEach((title) => expect(screen.getByText(title)).toBeTruthy());
});

test("the navigation shows how much is new, per section and per page", () => {
    renderNav("/news", { news_kingdom: 2, news_galaxy: 1, messages: 4, shared: 0 });

    expect(screen.getByText("Home (7)")).toBeTruthy();
    expect(screen.getByText(/News \(3\)/)).toBeTruthy();
    expect(screen.getByText(/Message \(4\)/)).toBeTruthy();
    expect(screen.getByText("Conquer")).toBeTruthy();
});

test("the navigation for someone not signed in is just landing and login", () => {
    render(
        <MemoryRouter><SideNavbar logged={false} showNav={true} setShowNav={() => {}} notifs={{}}/></MemoryRouter>
    );

    expect(screen.getByText("Login")).toBeTruthy();
    expect(screen.queryByText("Build")).toBeNull();
});
