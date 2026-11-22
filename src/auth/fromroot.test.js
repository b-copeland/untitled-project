import { fromRoot } from "./index";

test("an api path is asked for from the site's root, so nested pages like /kingdom/12 reach the API", () => {
    expect(fromRoot("api/kingdom/12")).toBe("/api/kingdom/12");
    expect(fromRoot("/api/state")).toBe("/api/state");
    expect(fromRoot("http://localhost:8000/api/state")).toBe("http://localhost:8000/api/state");
});
