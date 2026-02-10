import test from "node:test";
import assert from "node:assert/strict";
import { createEmptyGrid } from "./gameState.js";

test("createEmptyGrid creates a grid with expected dimensions", () => {
  const grid = createEmptyGrid(3, 4);

  assert.equal(grid.length, 3);
  assert.equal(grid[0].length, 4);
  assert.deepEqual(grid[2][3], { letter: "", status: "" });
});

test("createEmptyGrid creates unique cell objects", () => {
  const grid = createEmptyGrid(2, 2);

  grid[0][0].letter = "A";

  assert.equal(grid[0][1].letter, "");
  assert.equal(grid[1][0].letter, "");
});
