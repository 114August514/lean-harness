import { expect, test } from "bun:test";
import { add, loadSeeds } from "../src/index";

test("tracer add works", () => {
  expect(add(1, 2)).toBe(3);
});

test("tracer loadSeeds returns array", () => {
  expect(Array.isArray(loadSeeds())).toBe(true);
});
