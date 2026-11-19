import { expect, test } from "bun:test";
import { loadSeeds } from "../src/index";

test("loadSeeds reads items", () => {
	expect(loadSeeds('[{"id": "a", "title": "A"}]')).toEqual([
		{ id: "a", title: "A" },
	]);
});

test("loadSeeds rejects a non-array document", () => {
	expect(() => loadSeeds('{"id": "a"}')).toThrow();
});
