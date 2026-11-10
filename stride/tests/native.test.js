import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createBridge } from '../js/native.js';

test('no shell: unavailable, calls resolve with an error instead of throwing', async () => {
  const b = createBridge(undefined, {});
  assert.equal(b.available, false);
  assert.deepEqual(await b.requestPermission(), { ok: false, error: 'unavailable' });
});

test('readSteps passes the day range as millisecond strings and resolves with the reply', async () => {
  const scope = {}, calls = [];
  const b = createBridge({ readSteps: (id, s, e) => { calls.push([id, s, e]); queueMicrotask(() => scope.__strideNative.resolve(id, { ok: true, steps: 8123 })); } }, scope);
  const start = new Date(2026, 10, 10), end = new Date(2026, 10, 11);
  assert.deepEqual(await b.readSteps(start, end), { ok: true, steps: 8123 });
  assert.deepEqual(calls, [[1, String(start.getTime()), String(end.getTime())]]);
});

test('replies are matched by id, late and duplicate replies are ignored', async () => {
  const scope = {}, ids = [];
  const b = createBridge({ requestPermission: (id) => ids.push(id) }, scope);
  const first = b.requestPermission(), second = b.requestPermission();
  scope.__strideNative.resolve(ids[1], { ok: true });
  scope.__strideNative.resolve(ids[0], { ok: false, error: 'no_permission' });
  scope.__strideNative.resolve(ids[0], { ok: true });
  scope.__strideNative.resolve(999, { ok: true });
  assert.deepEqual(await first, { ok: false, error: 'no_permission' });
  assert.deepEqual(await second, { ok: true });
});

test('a throwing shell, a silent shell and a malformed reply all become errors', async () => {
  const scope = {};
  const b = createBridge({ shareText() { throw new Error('boom'); }, saveFile() {}, openHealthConnect: (id) => scope.__strideNative.resolve(id, 'nope') }, scope, 20);
  assert.deepEqual(await b.shareText('x'), { ok: false, error: 'bridge', message: 'boom' });
  assert.deepEqual(await b.saveFile('a.json', '{}'), { ok: false, error: 'timeout' });
  assert.deepEqual(await b.openHealthConnect(), { ok: false, error: 'bad_reply' });
});
