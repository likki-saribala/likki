// Bridge to the Android shell (stride-android). In a plain browser `available` is false.
// Calls are async: JS passes a request id, the shell answers through __strideNative.resolve(id, reply).
// Every reply is { ok: true, ... } or { ok: false, error: <code>, message? }.

export function createBridge(native, scope = globalThis, timeoutMs = 20000) {
  let seq = 0;
  const waiting = new Map();
  const settle = (id, reply) => { const w = waiting.get(id); if (!w) return; waiting.delete(id); clearTimeout(w.timer); w.resolve(reply); };
  scope.__strideNative = { resolve: (id, reply) => settle(id, reply && typeof reply === 'object' ? reply : { ok: false, error: 'bad_reply' }) };

  const call = (method, ...args) => new Promise((resolve) => {
    if (!native || typeof native[method] !== 'function') return resolve({ ok: false, error: 'unavailable' });
    const id = (seq += 1);
    const timer = timeoutMs ? setTimeout(() => settle(id, { ok: false, error: 'timeout' }), timeoutMs) : null;
    waiting.set(id, { resolve, timer });
    try { native[method](id, ...args); } catch (err) { settle(id, { ok: false, error: 'bridge', message: String(err?.message ?? err) }); }
  });

  return {
    available: Boolean(native),
    /** Total steps for one local calendar day given as [start, end) Date objects. */
    readSteps: (start, end) => call('readSteps', String(start.getTime()), String(end.getTime())),
    requestPermission: () => call('requestPermission'),
    openHealthConnect: () => call('openHealthConnect'),
    shareText: (text) => call('shareText', text),
    saveFile: (name, text) => call('saveFile', name, text),
  };
}

export const HEALTH_MESSAGES = {
  no_permission: 'Stride is not allowed to read your steps yet.',
  unavailable: 'Health Connect is not available on this phone.',
  update_required: 'Health Connect needs to be installed or updated.',
  timeout: 'Health Connect did not answer. Try again.',
};
