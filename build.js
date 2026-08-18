// Inlines src/msmed.js into web/index.html to produce a single self-contained
// docs/index.html. No bundler, no dependencies.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const MODULES = ['src/msmed.js'];
const PLACEHOLDER = '/*__ENGINE__*/';

const bundle = MODULES.map((file) => {
  const stripped = readFileSync(join(root, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+'[^']*';[ \t]*$/gm, '')
    .replace(/^export\s+/gm, '')
    .trim();
  for (const banned of [/^import\s/m, /^export\s/m]) {
    if (banned.test(stripped)) throw new Error(`${file}: module syntax survived stripping`);
  }
  return `/* ---------- ${file} ---------- */\n${stripped}`;
}).join('\n\n');

const shell = readFileSync(join(root, 'web/index.html'), 'utf8');
if (!shell.includes(PLACEHOLDER)) throw new Error(`web/index.html is missing ${PLACEHOLDER}`);

const output = shell.replace(PLACEHOLDER, () => bundle);
mkdirSync(join(root, 'docs'), { recursive: true });
writeFileSync(join(root, 'docs/index.html'), output, 'utf8');

console.log(`built docs/index.html  (${(output.length / 1024).toFixed(1)} KB)`);
