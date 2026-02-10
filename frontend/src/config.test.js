import test from "node:test";
import assert from "node:assert/strict";
import { LETTER_STATUS, STATUS_PRIORITY } from "./config.js";

test("STATUS_PRIORITY ranks status values from strongest to weakest", () => {
  assert.ok(
    STATUS_PRIORITY[LETTER_STATUS.correct] > STATUS_PRIORITY[LETTER_STATUS.present]
  );
  assert.ok(
    STATUS_PRIORITY[LETTER_STATUS.present] > STATUS_PRIORITY[LETTER_STATUS.absent]
  );
});
