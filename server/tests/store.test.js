import assert from "node:assert/strict";
import { describe, it } from "node:test";
import User from "../../data/models/User.js";

describe("user persistence", () => {
  it("requires age on the mongoose schema", () => {
    assert.equal(User.schema.path("age").isRequired, true);
    assert.equal(User.schema.path("age").options.min, 21);
    assert.equal(User.schema.path("age").options.max, 60);
  });
});
