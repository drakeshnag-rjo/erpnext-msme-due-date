// Executes the built page against a minimal DOM stub.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const builtPath = join(root, 'docs/index.html');

execFileSync(process.execPath, [join(root, 'build.js')], { cwd: root });
assert.ok(existsSync(builtPath), 'build did not produce docs/index.html');
const html = readFileSync(builtPath, 'utf8');

function makeNode(id = '') {
  return {
    id, tagName: '', children: [], style: {}, _text: '', _html: '',
    className: '', value: '', checked: false, listeners: {},
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); if (v === '') this.children = []; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); },
  };
}

function buildDom(source) {
  const nodes = new Map();
  for (const [, id] of source.matchAll(/\sid="([^"]+)"/g)) {
    if (!nodes.has(id)) nodes.set(id, makeNode(id));
  }
  for (const [, attrs] of source.matchAll(/<input\b([^>]*)>/g)) {
    const id = /\sid="([^"]+)"/.exec(attrs)?.[1];
    if (!id) continue;
    nodes.get(id).value = /\svalue="([^"]*)"/.exec(attrs)?.[1] ?? '';
    nodes.get(id).checked = /\schecked/.test(attrs);
  }
  for (const [, attrs, body] of source.matchAll(/<select\b([^>]*)>([\s\S]*?)<\/select>/g)) {
    const id = /\sid="([^"]+)"/.exec(attrs)?.[1];
    if (!id) continue;
    const opts = [...body.matchAll(/<option\s+value="([^"]*)"([^>]*)>/g)];
    const chosen = opts.find((o) => /\bselected\b/.test(o[2])) ?? opts[0];
    nodes.get(id).value = chosen ? chosen[1] : '';
  }
  return {
    nodes,
    document: {
      getElementById: (id) => nodes.get(id) ?? null,
      createElement: (t) => { const n = makeNode(); n.tagName = t.toUpperCase(); return n; },
    },
  };
}

function runPage() {
  const script = /<script>([\s\S]*)<\/script>/.exec(html);
  assert.ok(script, 'no <script> block');
  const dom = buildDom(html);
  new Function('document', script[1])(dom.document);
  return dom;
}

test('the page is self-contained apart from the issue hyperlink', () => {
  assert.ok(!/<script[^>]+\ssrc=/.test(html), 'external script');
  assert.ok(!/<link[^>]+stylesheet/.test(html), 'external stylesheet');
  const urls = [...html.matchAll(/https?:\/\/[^"'\s<>]+/g)].map((m) => m[0]);
  assert.deepEqual([...new Set(urls)], ['https://github.com/frappe/erpnext/issues/42807']);
  assert.ok(!/^\s*(import|export)\s/m.test(html), 'module syntax survived');
});

test('every colour token is defined on bare :root and redefined in dark', () => {
  const bare = /:root\s*\{([\s\S]*?)\}/.exec(html)[1];
  const dark = /:root\[data-theme="dark"\]\s*\{([\s\S]*?)\}/.exec(html)[1];
  const declared = new Set([...bare.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
  const used = new Set([...html.matchAll(/var\((--[\w-]+)\)/g)].map((m) => m[1]));
  assert.deepEqual([...used].filter((v) => !declared.has(v)), []);
  const colours = (b) => new Set([...b.matchAll(/(--[\w-]+)\s*:\s*(#|rgba)/g)].map((m) => m[1]));
  assert.deepEqual([...colours(bare)].filter((t) => !colours(dark).has(t)), []);
});

test('the redline device is used for all three corrections', () => {
  const dels = html.match(/<del>/g) || [];
  const inss = html.match(/<ins>/g) || [];
  assert.equal(dels.length, 3, 'expected one struck phrase per correction');
  assert.equal(inss.length, 3, 'expected one inserted phrase per correction');
});

test('the page renders without throwing', () => {
  const dom = runPage();
  assert.ok(dom.nodes.size > 12);
});

test('the default case shows Net 90 capped to 45 days', () => {
  const { nodes } = runPage();
  assert.equal(nodes.get('vAllowed').textContent, '45d');
  assert.equal(nodes.get('vDue').textContent, '2026-05-16');
  assert.equal(nodes.get('vAppointed').textContent, '2026-05-17');
  assert.equal(nodes.get('v43bh').textContent, 'Yes');
  assert.equal(nodes.get('outAllowed').className, 'out is-capped');
  assert.match(nodes.get('verdict').textContent, /void as to the additional 45 days/);
});

test('CORRECTION 1 is live: dropping the written agreement halves the period', () => {
  const { nodes } = runPage();
  nodes.get('hasWrittenAgreement').checked = false;
  nodes.get('controls').listeners.change[0]();
  assert.equal(nodes.get('vAllowed').textContent, '15d');
  assert.equal(nodes.get('vDue').textContent, '2026-04-16');
  assert.match(nodes.get('verdict').textContent, /no written agreement/);
});

test('CORRECTION 2 is live: a medium supplier keeps its contract', () => {
  const { nodes } = runPage();
  nodes.get('category').value = 'Medium';
  nodes.get('controls').listeners.change[0]();
  assert.equal(nodes.get('vAllowed').textContent, '90d');
  assert.equal(nodes.get('vDue').textContent, '2026-06-30');
  assert.equal(nodes.get('vAppointed').textContent, 'n/a');
  assert.equal(nodes.get('v43bh').textContent, 'No');
  assert.equal(nodes.get('verdict').className, 'verdict is-unprotected');
});

test('CORRECTION 3 is live: a trader loses 43B(h) but keeps the clock', () => {
  const { nodes } = runPage();
  nodes.get('isTrader').checked = true;
  nodes.get('controls').listeners.change[0]();
  assert.equal(nodes.get('v43bh').textContent, 'No');
  assert.equal(nodes.get('vAllowed').textContent, '45d'); // s.15 still applies
});

test('the comparison table is computed, and quantifies the error', () => {
  const { nodes } = runPage();
  const rows = nodes.get('comparisonRows').children;
  assert.equal(rows.length, 4);
  const drift = rows.map((r) => r.children[3].textContent);
  // Net 90 written happens to coincide; the other three do not.
  assert.deepEqual(drift, ['—', '-30 days', '-15 days', '+45 days']);
  // The wrong figures are marked as wrong.
  assert.equal(rows[1].children[1].className, 'mono wrong');
  assert.equal(rows[1].children[2].className, 'mono right');
  assert.equal(rows[0].children[1].className, 'mono');
});
