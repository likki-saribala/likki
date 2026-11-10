// Single-user, on-device storage. Nothing leaves the phone.
const KEY = 'stride.v1';

export const pad = (n) => String(n).padStart(2, '0');
export const keyOf = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const todayKey = () => keyOf(new Date());
export const dateOf = (k) => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
export const shiftKey = (k, n) => { const d = dateOf(k); d.setDate(d.getDate() + n); return keyOf(d); };

export const newDay = () => ({
  steps: 0,
  checks: { walk: false, run: false, diet: false },
  gym: { done: false, minutes: 60, intensity: 'moderate', exercises: [] },
  meals: { breakfast: [], lunch: [], snacks: [], dinner: [] },
});

const blank = () => ({ profile: null, days: {}, myFoods: [] });

function read() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return blank();
    const d = JSON.parse(raw);
    return { ...blank(), ...d };
  } catch (err) {
    console.error('Stride: could not read saved data', err);
    return blank();
  }
}

let data = read();
let saveError = null;

export const store = {
  get data() { return data; },
  get profile() { return data.profile; },
  get saveError() { return saveError; },
  /** Day for editing (created on first write access). */
  day(k) { return (data.days[k] ??= newDay()); },
  /** Day for reading; never creates. */
  peek(k) { return data.days[k] ?? newDay(); },
  save() {
    try { localStorage.setItem(KEY, JSON.stringify(data)); saveError = null; }
    catch (err) { saveError = err; console.error('Stride: save failed', err); }
    return !saveError;
  },
  replace(next) {
    if (!next || typeof next !== 'object' || typeof next.days !== 'object') throw new Error('Not a Stride backup file');
    data = { ...blank(), ...next };
    return this.save();
  },
  reset() { data = blank(); localStorage.removeItem(KEY); },
};
