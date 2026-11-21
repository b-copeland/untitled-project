import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MilitaryContent from "./military";
import { authFetch } from "../../auth";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));
beforeEach(() => {
    authFetch.mockImplementation(() => Promise.resolve({ json: () => Promise.resolve({ status: "success", message: "ok" }) }));
});

const unit = (cost, offense, defense) => ({ cost, offense, defense, fuel: 1, hangar_capacity: 1 });
const data = () => ({
    kingdom: { money: 10000, units: { recruits: 50, attack: 5, defense: 0, flex: 0, big_flex: 0, engineers: 3 },
               completed_projects: [], units_target: { attack: 0.5 } },
    mobis: {
        units_desc: { attack: unit(100, 5, 0), defense: unit(100, 0, 5), flex: unit(200, 4, 4), big_flex: { ...unit(500, 8, 8), project: "big_flexers" }, recruits: { offense: 0, defense: 1 } },
        units: { current_total: { attack: 5, recruits: 50 }, hour_24: {}, current: { recruits: 50 } },
        current_hangar_capacity: 50, max_hangar_capacity: 100, recruit_price: 10, recruit_time: 3600,
        current_available_recruits: 10, max_available_recruits: 10,
    },
    state: { pretty_names: { attack: "Attackers", defense: "Defenders", flex: "Flexers", big_flex: "Big Flexers" },
             projects: { big_flexers: { name: "Big Flexers" } }, game_config: {} },
});
const show = () => render(<MilitaryContent data={data()} loading={{}} updateData={jest.fn()} />);

test("one table, and the switch changes only what you are doing with it", () => {
    show();
    expect(screen.queryByText("Levy")).toBeNull();
    expect(screen.getByText("To Train")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Allocate" }));
    expect(screen.getByText("New Share")).toBeTruthy();
    expect(screen.getByText("50.0%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Disband" }));
    expect(screen.getByText("To Disband")).toBeTruthy();
    expect(screen.getAllByRole("table")).toHaveLength(1);
});

test("hangar space is shown, and a locked unit says what unlocks it", () => {
    show();
    expect(screen.getByText("50 / 100 (50.0%)")).toBeTruthy();
    expect(screen.getByText('Research "Big Flexers" to unlock')).toBeTruthy();
    expect(document.getElementById("big_flex-train-input").disabled).toBe(true);
});

test("training waits for units, and the slider stops at the recruits you have", () => {
    show();
    const train = () => screen.getByRole("button", { name: "Train units" });
    expect(train().disabled).toBe(true);
    expect(train().title).toBe("Choose some units to train");
    fireEvent.change(document.getElementById("attack-train-input"), { target: { value: "20" } });
    expect(train().disabled).toBe(false);
    fireEvent.change(document.getElementById("attack-train-input"), { target: { value: "60" } });  // only 50 recruits
    expect(document.getElementById("attack-train-input").value).toBe("50");
    expect(train().disabled).toBe(false);
});

const withUpgrades = () => {
    const d = data();
    d.kingdom.units = { ...d.kingdom.units, attack: 10, heavy_attack: 4 };
    d.kingdom.completed_projects = ["heavy_attackers", "elite_attackers"];
    d.mobis.units_desc = {
        ...d.mobis.units_desc,
        heavy_attack: { ...unit(400, 6, 0), project: "heavy_attackers", upgrades_from: "attack", upgrade_cost: 100 },
        elite_attack: { ...unit(525, 7, 0), project: "elite_attackers", upgrades_from: "heavy_attack", upgrade_cost: 125 },
        solar_attack: { ...unit(600, 7, 0), project: "solar_attackers", upgrades_from: "elite_attack", upgrade_cost: 75 },
    };
    d.state.pretty_names = { ...d.state.pretty_names, heavy_attack: "Heavy Attackers", elite_attack: "Elite Attackers", solar_attack: "Solar Attackers" };
    d.state.projects = { ...d.state.projects, solar_attackers: { name: "Solar Attackers" } };
    return d;
};

test("the Upgrade page lists only units made from others, with where they come from and the server's cost", () => {
    render(<MilitaryContent data={withUpgrades()} loading={{}} updateData={jest.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Upgrade" }));
    expect(document.getElementById("attack-upgrade-input")).toBeNull();
    expect(document.getElementById("heavy_attack-upgrade-input")).not.toBeNull();
    expect(screen.getByText("Attackers (10 at home)")).toBeTruthy();
    expect(screen.getByText("Heavy Attackers (4 at home)")).toBeTruthy();
    expect(screen.getByText("125")).toBeTruthy();
    expect(document.getElementById("solar_attack-upgrade-input").disabled).toBe(true);  // project not done
});

test("an upgrade stops at the units at home, and sends what was chosen", async () => {
    const updateData = jest.fn((keys, funcs) => funcs.forEach((f) => f()));
    render(<MilitaryContent data={withUpgrades()} loading={{}} updateData={updateData} />);
    fireEvent.click(screen.getByRole("button", { name: "Upgrade" }));
    const button = () => screen.getByRole("button", { name: "Upgrade units" });
    expect(button().title).toBe("Choose some units to upgrade");
    fireEvent.change(document.getElementById("heavy_attack-upgrade-input"), { target: { value: "50" } });
    expect(document.getElementById("heavy_attack-upgrade-input").value).toBe("10");  // 10 attackers at home
    expect(screen.getByText("Cost: 1,000")).toBeTruthy();
    fireEvent.click(button());
    expect(authFetch).toHaveBeenCalledWith("api/mobis/upgrade", expect.objectContaining({
        body: JSON.stringify({ input: { heavy_attack: "10", elite_attack: "", solar_attack: "" } }),
    }));
    expect(await screen.findByText("ok")).toBeTruthy();
});

test("the Disband page offers recruits and the trained units, but not engineers", () => {
    show();
    fireEvent.click(screen.getByRole("button", { name: "Disband" }));
    expect(document.getElementById("disband-attack")).not.toBeNull();
    expect(document.getElementById("disband-recruits")).not.toBeNull();
    expect(document.getElementById("disband-engineers")).toBeNull();
});
