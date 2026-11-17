import { availableOperations } from "./spy";

jest.mock("../../components/header", () => () => null);
jest.mock("../../components/helpbutton", () => () => null);
jest.mock("../../auth", () => ({ authFetch: jest.fn() }));

const operations = [{ value: "spykingdom" }, { value: "spyall" }];
const state = { operation_projects: { spyall: "vult_evolution" } };

test("an operation that needs a project is offered only once the project is done", () => {
    expect(availableOperations(operations, { completed_projects: [] }, state).map((op) => op.value)).toEqual(["spykingdom"]);
    expect(availableOperations(operations, { completed_projects: ["vult_evolution"] }, state).map((op) => op.value))
        .toEqual(["spykingdom", "spyall"]);
});

test("without the server's list every operation is offered", () => {
    expect(availableOperations(operations, {}, {})).toHaveLength(2);
});
