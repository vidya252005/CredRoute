import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildPayload, validateForm } from "../../client/src/lib/validation.js";
import { presets } from "../../client/src/lib/presets.js";

describe("client form validation", () => {
  it("accepts a valid prime preset", () => {
    const errors = validateForm(presets.prime);
    assert.deepEqual(errors, {});
  });

  it("accepts thin-file when CIBIL is blank", () => {
    const errors = validateForm(presets.thinFile);
    assert.deepEqual(errors, {});
  });

  it("rejects an invalid PAN", () => {
    const errors = validateForm({ ...presets.prime, pan: "INVALID" });
    assert.match(errors.pan, /PAN must match/);
  });

  it("rejects CIBIL below 300", () => {
    const errors = validateForm({ ...presets.prime, cibilScore: 1 });
    assert.match(errors.cibilScore, /300 and 900/);
  });

  it("rejects age outside 21-60", () => {
    const errors = validateForm({ ...presets.prime, age: 18 });
    assert.match(errors.age, /21 and 60/);
    const tooOld = validateForm({ ...presets.prime, age: 65 });
    assert.match(tooOld.age, /21 and 60/);
  });

  it("rejects when alt-data consent is missing", () => {
    const errors = validateForm({ ...presets.prime, consentAltData: false });
    assert.match(errors.consentAltData, /Consent/);
  });

  it("builds a normalized API payload", () => {
    const payload = buildPayload(presets.thinFile);
    assert.equal(payload.pan, "FGHIJ5678K");
    assert.equal(payload.cibilScore, null);
    assert.equal(payload.tenureMonths, 12);
  });
});
