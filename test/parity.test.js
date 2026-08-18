// The JavaScript port must reproduce the Python reference implementation
// exactly, on every generated vector. If the two ever disagree, the published
// page is describing rules that the mergeable module does not implement.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  statutoryDueDate,
  isoDate,
  classifyEnterprise,
  dayOfAcceptance,
  is43BhApplicable,
  statutoryMaxDays,
  MICRO,
  SMALL,
  MEDIUM,
  LARGE,
} from '../src/msmed.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const vectors = JSON.parse(readFileSync(join(root, 'vectors.json'), 'utf8'));

test('the vector file is present and substantial', () => {
  assert.ok(Array.isArray(vectors));
  assert.ok(vectors.length >= 200, `only ${vectors.length} vectors`);
});

test('CONFORMANCE: the JS port matches the Python reference on every vector', () => {
  let checked = 0;
  for (const { input, expected } of vectors) {
    const r = statutoryDueDate(input);
    const actual = {
      protected: r.protected,
      allowedDays: r.allowedDays,
      dueDate: isoDate(r.dueDate),
      appointedDate: r.appointedDate ? isoDate(r.appointedDate) : null,
      capped: r.capped,
      voidedDays: r.voidedDays,
    };
    assert.deepEqual(actual, expected, `mismatch for ${JSON.stringify(input)}`);
    checked++;
  }
  assert.equal(checked, vectors.length);
});

/* ---------- the rules the page asserts in prose ---------- */

test('classification sits exactly on the 2025 thresholds', () => {
  assert.equal(classifyEnterprise(2.5, 10), MICRO);
  assert.equal(classifyEnterprise(25, 100), SMALL);
  assert.equal(classifyEnterprise(125, 500), MEDIUM);
  assert.equal(classifyEnterprise(125.01, 500), LARGE);
  // Low investment, high turnover — the trap for a trading business.
  assert.equal(classifyEnterprise(0.5, 300), MEDIUM);
});

test('CORRECTION 1: no written agreement means 15 days, not 45', () => {
  assert.equal(statutoryMaxDays(true), 45);
  assert.equal(statutoryMaxDays(false), 15);
  const r = statutoryDueDate({
    acceptanceDate: '2026-04-01',
    agreedDays: 45,
    hasWrittenAgreement: false,
  });
  assert.equal(r.allowedDays, 15);
  assert.equal(isoDate(r.dueDate), '2026-04-16');
});

test('CORRECTION 2: a medium supplier keeps its contractual period', () => {
  const r = statutoryDueDate({
    acceptanceDate: '2026-04-01',
    agreedDays: 90,
    category: MEDIUM,
  });
  assert.equal(r.protected, false);
  assert.equal(r.allowedDays, 90);
  assert.equal(isoDate(r.dueDate), '2026-06-30');
  assert.equal(r.appointedDate, null);
});

test('CORRECTION 3: traders keep s.15 but fall outside s.43B(h)', () => {
  assert.equal(is43BhApplicable(SMALL, true, false), true);
  assert.equal(is43BhApplicable(SMALL, true, true), false);
  assert.equal(is43BhApplicable(MEDIUM, true, false), false);
});

test('Net 90 is void beyond day 45, and interest starts the day after', () => {
  const r = statutoryDueDate({ acceptanceDate: '2026-04-01', agreedDays: 90 });
  assert.equal(r.allowedDays, 45);
  assert.equal(r.capped, true);
  assert.equal(r.voidedDays, 45);
  assert.equal(isoDate(r.dueDate), '2026-05-16');
  assert.equal(isoDate(r.appointedDate), '2026-05-17');
});

test('the objection window defers acceptance only when it is timely', () => {
  assert.equal(isoDate(dayOfAcceptance('2026-04-01')), '2026-04-01');
  // Raised on day 10, removed 25 April.
  assert.equal(isoDate(dayOfAcceptance('2026-04-01', '2026-04-11', '2026-04-25')), '2026-04-25');
  // Day 16 is outside the 15-day window, so acceptance stays at delivery.
  assert.equal(isoDate(dayOfAcceptance('2026-04-01', '2026-04-17', '2026-05-20')), '2026-04-01');
  // An unresolved objection does not move it either.
  assert.equal(isoDate(dayOfAcceptance('2026-04-01', '2026-04-05', null)), '2026-04-01');
});

test('dates are timezone-proof across a leap day', () => {
  const r = statutoryDueDate({ acceptanceDate: '2028-02-29', agreedDays: 45 });
  assert.equal(isoDate(r.dueDate), '2028-04-14');
});
