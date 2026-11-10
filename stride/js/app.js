import { store, todayKey, shiftKey, dateOf } from './store.js';
import * as C from './calc.js';
import { FOODS } from './foods.js';
import { resolveEntry, searchFoods, gramsFor, describe } from './foodparse.js';
import { EXERCISES } from './exercises.js';

const MEALS = [['breakfast', 'Breakfast'], ['lunch', 'Lunch'], ['snacks', 'Snacks'], ['dinner', 'Dinner']];
const TABS = [['today', 'Today'], ['gym', 'Gym'], ['food', 'Food'], ['report', 'Report']];
const DEFAULT_PROFILE = { sex: 'male', age: 25, heightCm: 170, weightKg: 70, goal: 'maintain', stepGoal: 10000, walkMin: 30, runMin: 30, autoTargets: true };
const RING_C = 2 * Math.PI * 96;

const svg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
const ICON = {
  today: svg('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  gym: svg('<path d="M6.5 8v8M17.5 8v8M3.5 10v4M20.5 10v4M6.5 12h11"/>'),
  food: svg('<path d="M7 3v7a2 2 0 0 0 2 2v9M11 3v7a2 2 0 0 1-2 2M9 3v6M17 21v-7h-2.5c0-6 1-10 2.5-11z"/>'),
  report: svg('<path d="M5 20V10M12 20V4M19 20v-7"/>'),
  prev: svg('<path d="M14.5 6l-6 6 6 6"/>'), next: svg('<path d="M9.5 6l6 6-6 6"/>'),
  gear: svg('<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8"/>'),
  tick: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 5"/></svg>',
};

const state = { tab: 'today', date: todayKey(), meal: mealForNow(), pending: null, online: null, anim: new Map(), locked: false };

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const n0 = (x) => Math.round(x || 0).toLocaleString('en-IN');
const n1 = (x) => C.round(x || 0, 1).toLocaleString('en-IN');
const profile = () => {
  const p = { ...DEFAULT_PROFILE, ...(store.profile ?? {}) };
  if (p.autoTargets || !p.targets) p.targets = C.suggestTargets(p);
  return p;
};
const day = () => store.peek(state.date);
const edit = () => store.day(state.date);
const allFoods = () => [...store.data.myFoods.map((f) => ({ ...f, aliases: [], aliasText: '', mine: true })), ...FOODS];

function mealForNow() { const h = new Date().getHours(); return h < 11 ? 'breakfast' : h < 16 ? 'lunch' : h < 19 ? 'snacks' : 'dinner'; }
function commit(opts) { if (!store.save()) toast('Could not save — storage is full or blocked'); render(opts); }

let toastTimer;
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2400);
}

/* ---------- animated primitives ---------- */
function ring(id, pct, mid) {
  const to = RING_C * (1 - Math.max(0, Math.min(1, pct)));
  const from = state.anim.get(id) ?? RING_C;
  return `<div class="ring"><svg viewBox="0 0 216 216"><circle class="track" cx="108" cy="108" r="96"/>
    <circle class="fill" cx="108" cy="108" r="96" data-anim="${id}" data-to="${to}" style="stroke-dasharray:${RING_C};stroke-dashoffset:${from}"/></svg>
    <div class="ring-mid">${mid}</div></div>`;
}
function bar(id, pct, color) {
  const to = `${Math.max(0, Math.min(100, pct * 100))}%`;
  return `<div class="bar"><i data-anim="${id}" data-prop="width" data-to="${to}" style="width:${state.anim.get(id) ?? '0%'};background:${color}"></i></div>`;
}
function runAnims() {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    for (const el of document.querySelectorAll('[data-anim]')) {
      el.style[el.dataset.prop || 'strokeDashoffset'] = el.dataset.to;
      state.anim.set(el.dataset.anim, el.dataset.to);
    }
  }));
}

/* ---------- views ---------- */
function topBar() {
  const today = todayKey(), d = dateOf(state.date);
  const title = state.date === today ? 'Today' : state.date === shiftKey(today, -1) ? 'Yesterday' : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long' });
  return `<button class="icon-btn" data-act="day:-1" aria-label="Previous day">${ICON.prev}</button>
    <button class="date" data-act="day:0" aria-label="Go to today"><small>${d.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}</small><strong>${title}</strong></button>
    <button class="icon-btn" data-act="day:1" aria-label="Next day" ${state.date >= today ? 'disabled' : ''}>${ICON.next}</button>
    <button class="icon-btn" data-act="settings" aria-label="Profile and targets">${ICON.gear}</button>`;
}

function check(key, on, title, sub, side = '') {
  return `<button class="check" role="checkbox" aria-checked="${on}" data-act="toggle:${key}">
    <span class="box">${ICON.tick}</span><span class="txt"><b>${title}</b><span>${sub}</span></span><span class="side num">${side}</span></button>`;
}

function macroBars(intake, t, prefix) {
  const rows = [['Protein', intake.p, t.protein, 'var(--protein)'], ['Carbs', intake.c, t.carbs, 'var(--carbs)'], ['Fat', intake.f, t.fat, 'var(--fat)']];
  return rows.map(([name, v, goal, color]) => `<div class="macro"><div class="row"><b>${name}</b><span class="num">${n0(v)} / ${n0(goal)} g</span></div>${bar(`${prefix}-${name}`, goal ? v / goal : 0, color)}</div>`).join('');
}

function viewToday() {
  const p = profile(), d = day(), burn = C.dayBurn(d, p), intake = C.dayIntake(d), t = p.targets;
  const pct = p.stepGoal ? d.steps / p.stepGoal : 0, left = Math.max(0, p.stepGoal - d.steps);
  const stepsDone = d.steps >= p.stepGoal && p.stepGoal > 0;
  const ws = C.workoutStats(d.gym), net = intake.kcal - burn.total;
  return `
  <section class="card hero">
    ${ring('steps', pct, `<span class="big num">${n0(d.steps)}</span><small>of ${n0(p.stepGoal)} steps</small>`)}
    <div class="stats">
      <div><b class="num">${n1(C.stepsToKm(d.steps, p.heightCm))}</b><span>km walked</span></div>
      <div><b class="num">${n0(burn.steps)}</b><span>kcal from steps</span></div>
      <div><b class="num">${stepsDone ? 'Done' : n0(left)}</b><span>${stepsDone ? 'goal reached' : 'steps to go'}</span></div>
    </div>
    <button class="btn ghost small" data-act="steps" style="margin-top:16px">Update steps</button>
  </section>
  <section class="card checks" aria-label="Daily checklist">
    ${check('walk', d.checks.walk, 'Morning walk', `${p.walkMin} min · counted in steps`)}
    ${check('run', d.checks.run, 'Morning run', `${p.runMin} min`, `+${n0(C.runExtraKcal(p.runMin, p.weightKg))} kcal`)}
    <div class="check" role="checkbox" aria-checked="${stepsDone}" aria-disabled="true">
      <span class="box" style="--pct:${Math.min(100, pct * 100)}%">${ICON.tick}</span>
      <span class="txt"><b>${n0(p.stepGoal)} steps</b><span>Ticks itself at the goal</span></span><span class="side num">${Math.min(100, Math.round(pct * 100))}%</span></div>
    ${check('gym', d.gym.done, 'Gym session', `${d.gym.minutes} min · ${d.gym.intensity}${ws.exercises ? ` · ${ws.exercises} exercises` : ''}`, `+${n0(C.gymKcal(d.gym.minutes, d.gym.intensity, p.weightKg))} kcal`)}
    ${check('diet', d.checks.diet, 'Ate on plan', `${n0(intake.kcal)} / ${n0(t.kcal)} kcal · ${n0(intake.p)} g protein`)}
  </section>
  <section class="card">
    <h2>Energy <b class="num">${net > 0 ? 'Surplus' : 'Deficit'} ${n0(Math.abs(net))} kcal</b></h2>
    <div class="energy">
      <div><b class="num c-acc">${n0(intake.kcal)}</b><span>eaten</span></div><i>−</i>
      <div><b class="num c-burn">${n0(burn.total)}</b><span>burned</span></div><i>=</i>
      <div><b class="num">${net > 0 ? '+' : '−'}${n0(Math.abs(net))}</b><span>net</span></div>
    </div>
    <p class="hint">Burned = ${n0(burn.rest)} at rest + ${n0(burn.active)} active. These are formula estimates, not measurements.</p>
  </section>
  <section class="card"><h2>Macros <b class="num">${n0(Math.max(0, t.kcal - intake.kcal))} kcal left</b></h2>${macroBars(intake, t, 'today')}</section>`;
}

function gymStatsText(d, p) {
  const ws = C.workoutStats(d.gym);
  return `${ws.sets} sets · ${n0(ws.volume)} kg lifted · est. ${n0(C.gymKcal(d.gym.minutes, d.gym.intensity, p.weightKg))} kcal`;
}

function lastWorkoutKey() {
  return Object.keys(store.data.days).filter((k) => k < state.date && store.data.days[k].gym.exercises.length).sort().pop();
}

function viewGym() {
  const p = profile(), d = day(), g = d.gym;
  const lastKey = lastWorkoutKey();
  const exercises = g.exercises.map((ex, i) => `
    <section class="card">
      <div class="ex-head"><b>${esc(ex.name)}</b><button class="x" data-act="del-ex:${i}" aria-label="Remove ${esc(ex.name)}">×</button></div>
      ${ex.sets.map((s, j) => `<div class="set"><span>${j + 1}</span>
        <label><input class="in num" inputmode="numeric" data-in="set:${i}:${j}:reps" value="${esc(s.reps)}" aria-label="Set ${j + 1} reps"><em>reps</em></label><span>×</span>
        <label><input class="in num" inputmode="decimal" data-in="set:${i}:${j}:kg" value="${esc(s.kg)}" aria-label="Set ${j + 1} weight in kg"><em>kg</em></label>
        <button class="x" data-act="del-set:${i}:${j}" aria-label="Remove set ${j + 1}">×</button></div>`).join('')}
      <button class="link" data-act="add-set:${i}">+ Add set</button>
    </section>`).join('');
  return `
  <section class="card">
    <h2>Session <b id="gym-stats" class="num">${gymStatsText(d, p)}</b></h2>
    <div class="seg" role="group" aria-label="Intensity">${['light', 'moderate', 'intense'].map((v) => `<button data-act="intensity:${v}" aria-pressed="${g.intensity === v}">${v[0].toUpperCase() + v.slice(1)}</button>`).join('')}</div>
    <div class="field-row" style="margin-top:8px"><span>Duration</span>
      <div class="stepper"><button data-act="gym-min:-5" aria-label="5 minutes less">−</button><b class="num">${g.minutes} min</b><button data-act="gym-min:5" aria-label="5 minutes more">+</button></div></div>
    <div class="field-row"><span>${g.done ? 'Session completed' : 'Not marked done yet'}</span>
      <button class="btn small ${g.done ? 'ghost' : ''}" data-act="toggle:gym">${g.done ? 'Undo' : 'Mark done'}</button></div>
  </section>
  ${exercises || `<div class="empty"><b>No exercises yet</b>Add what you trained and log each set.</div>`}
  <div class="row" style="margin-top:4px"><button class="btn block" data-act="add-ex">Add exercise</button>
    ${!g.exercises.length && lastKey ? `<button class="btn ghost block" data-act="repeat-last">Repeat last workout</button>` : ''}</div>`;
}

function recentFoods() {
  const seen = new Map();
  for (let i = 0, k = state.date; i < 14; i += 1, k = shiftKey(k, -1)) {
    const d = store.data.days[k]; if (!d) continue;
    for (const it of C.dayItems(d)) { const r = seen.get(it.name) ?? { n: 0, it }; r.n += 1; seen.set(it.name, r); }
  }
  return [...seen.values()].sort((a, b) => b.n - a.n).slice(0, 8).map((r) => r.it);
}

function viewFood() {
  const p = profile(), d = day(), intake = C.dayIntake(d), t = p.targets;
  const recents = recentFoods(); state.recents = recents;
  const yKey = shiftKey(state.date, -1), y = store.data.days[yKey];
  const meals = MEALS.map(([key, label]) => {
    const items = d.meals[key], sum = C.sumMacros(items);
    const copy = !items.length && y?.meals[key].length ? `<button class="link" data-act="copy-meal:${key}">Copy yesterday’s ${label.toLowerCase()}</button>` : '';
    if (!items.length && !copy) return '';
    return `<section class="card"><h2>${label} <b class="num">${n0(sum.kcal)} kcal · ${n0(sum.p)} g protein</b></h2>
      ${items.map((it, i) => { const m = C.itemMacros(it); return `<div class="item">
        <button class="txt" data-act="edit-item:${key}:${i}" style="text-align:left"><b>${esc(it.name)}</b><span>${/ (g|ml)$/.test(it.label) ? `${n0(it.grams)} g` : `${esc(it.label)} · ${n0(it.grams)} g`}</span></button>
        <div class="k num">${n0(m.kcal)}<small>${n1(m.p)} g P</small></div>
        <button class="x" data-act="del-item:${key}:${i}" aria-label="Remove ${esc(it.name)}">×</button></div>`; }).join('')}${copy}</section>`;
  }).join('');
  return `
  <section class="card">
    <div class="total">
      <div><b class="num c-acc">${n0(intake.kcal)}</b><span>of ${n0(t.kcal)} kcal</span></div>
      <div><b class="num" style="color:var(--protein)">${n0(intake.p)}</b><span>protein g</span></div>
      <div><b class="num" style="color:var(--carbs)">${n0(intake.c)}</b><span>carbs g</span></div>
      <div><b class="num" style="color:var(--fat)">${n0(intake.f)}</b><span>fat g</span></div>
    </div>
    <div style="margin-top:14px">${bar('food-kcal', t.kcal ? intake.kcal / t.kcal : 0, 'var(--accent)')}</div>
  </section>
  <section class="card composer">
    <div class="chips" role="group" aria-label="Meal">${MEALS.map(([k, l]) => `<button class="chip" data-act="meal:${k}" aria-pressed="${state.meal === k}">${l}</button>`).join('')}</div>
    <textarea id="food-text" class="in" rows="2" placeholder="2 roti, 1 katori dal, 150g chicken breast" aria-label="What did you eat?"></textarea>
    <button class="btn block" data-act="add-food">Add to ${MEALS.find(([k]) => k === state.meal)[1].toLowerCase()}</button>
    ${recents.length ? `<div class="chips" aria-label="Recent foods">${recents.map((it, i) => `<button class="chip" data-act="quick:${i}">+ ${esc(it.label)} ${esc(it.name)}</button>`).join('')}</div>` : ''}
  </section>
  ${meals || `<div class="empty"><b>Nothing logged yet</b>Type your meal above with amounts, separated by commas.</div>`}`;
}

function viewReport() {
  const p = profile(), d = day(), burn = C.dayBurn(d, p), intake = C.dayIntake(d), t = p.targets, ws = C.workoutStats(d.gym);
  const score = C.dayScore(d, p), run = C.streak(store.data.days, p, todayKey(), (k) => shiftKey(k, -1));
  const net = intake.kcal - burn.total;
  const keys = Array.from({ length: 7 }, (_, i) => shiftKey(state.date, i - 6));
  const week = keys.map((k) => store.peek(k));
  const logged = keys.filter((k) => store.data.days[k]).length || 1;
  const maxSteps = Math.max(p.stepGoal, ...week.map((x) => x.steps), 1);
  const avg = (f) => week.reduce((s, x) => s + f(x), 0) / logged;
  const verdict = score >= 100 ? 'Perfect day' : score >= 80 ? 'Strong day' : score >= 50 ? 'Halfway there' : score > 0 ? 'Just getting started' : 'Nothing logged yet';
  const li = (on, label, val) => `<li><div><i class="dot ${on ? 'on' : ''}"></i>${label}</div><span class="num">${val}</span></li>`;
  return `
  <section class="card score">
    ${ring('score', score / 100, `<span class="big num">${score}</span>`)}
    <div><h3>${verdict}</h3><div class="hint" style="margin:0">${run ? `${run}-day streak of 80+ days` : 'Score 80 or more to start a streak'}</div></div>
  </section>
  <section class="card"><h2>Checklist</h2><ul class="done-list">
    ${li(d.checks.walk, 'Morning walk', `${p.walkMin} min`)}${li(d.checks.run, 'Morning run', `${p.runMin} min`)}
    ${li(d.steps >= p.stepGoal, 'Steps', `${n0(d.steps)} · ${n1(C.stepsToKm(d.steps, p.heightCm))} km`)}
    ${li(d.gym.done, 'Gym', d.gym.done ? `${d.gym.minutes} min · ${d.gym.intensity}` : 'not done')}${li(d.checks.diet, 'Ate on plan', `${n0(intake.kcal)} kcal`)}
  </ul></section>
  <section class="card"><h2>Energy</h2><div class="grid2">
    <div class="tile"><span>Eaten</span><b class="num">${n0(intake.kcal)}</b><small>/ ${n0(t.kcal)}</small></div>
    <div class="tile"><span>Burned (est.)</span><b class="num">${n0(burn.total)}</b><small>kcal</small></div>
    <div class="tile"><span>${net > 0 ? 'Surplus' : 'Deficit'}</span><b class="num">${n0(Math.abs(net))}</b><small>kcal</small></div>
    <div class="tile"><span>Active burn</span><b class="num">${n0(burn.active)}</b><small>kcal</small></div>
  </div><div style="margin-top:16px">${macroBars(intake, t, 'rep')}</div></section>
  ${ws.exercises ? `<section class="card"><h2>Workout <b class="num">${ws.sets} sets · ${n0(ws.volume)} kg</b></h2><ul class="done-list">
    ${d.gym.exercises.map((ex) => `<li><div>${esc(ex.name)}</div><span class="num">${ex.sets.filter((s) => +s.reps).map((s) => `${esc(s.reps)}×${esc(s.kg || 0)}`).join(', ') || '—'}</span></li>`).join('')}</ul></section>` : ''}
  <section class="card"><h2>Last 7 days <b class="num">${n0(avg((x) => x.steps))} steps/day</b></h2>
    <div class="week">${week.map((x, i) => `<button class="col ${x.steps >= p.stepGoal ? 'hit' : ''} ${keys[i] === state.date ? 'sel' : ''}" data-act="goto:${keys[i]}" aria-label="${dateOf(keys[i]).toDateString()}: ${n0(x.steps)} steps">
      <div data-anim="wk-${keys[i]}" data-prop="height" data-to="${Math.round((x.steps / maxSteps) * 100)}%" style="height:${state.anim.get(`wk-${keys[i]}`) ?? '0%'}"></div><span>${dateOf(keys[i]).toLocaleDateString('en-IN', { weekday: 'narrow' })}</span></button>`).join('')}</div>
    <div class="grid2" style="margin-top:16px">
      <div class="tile"><span>Avg eaten</span><b class="num">${n0(avg((x) => C.dayIntake(x).kcal))}</b><small>kcal</small></div>
      <div class="tile"><span>Avg protein</span><b class="num">${n0(avg((x) => C.dayIntake(x).p))}</b><small>g</small></div>
      <div class="tile"><span>Gym sessions</span><b class="num">${week.filter((x) => x.gym.done).length}</b><small>of 7</small></div>
      <div class="tile"><span>Runs</span><b class="num">${week.filter((x) => x.checks.run).length}</b><small>of 7</small></div>
    </div><p class="hint">Averages cover the ${logged} day${logged > 1 ? 's' : ''} with data.</p></section>
  <button class="btn ghost block" data-act="share">Share this report</button>`;
}

function reportText() {
  const p = profile(), d = day(), burn = C.dayBurn(d, p), intake = C.dayIntake(d), ws = C.workoutStats(d.gym), y = (b) => (b ? 'yes' : 'no');
  return [`Stride report — ${dateOf(state.date).toDateString()}`, `Score: ${C.dayScore(d, p)}/100`,
    `Steps: ${n0(d.steps)} (${n1(C.stepsToKm(d.steps, p.heightCm))} km)`, `Walk: ${y(d.checks.walk)} · Run: ${y(d.checks.run)} · Gym: ${y(d.gym.done)} · Diet on plan: ${y(d.checks.diet)}`,
    ws.exercises ? `Workout: ${d.gym.intensity}, ${d.gym.minutes} min, ${ws.sets} sets, ${n0(ws.volume)} kg lifted` : null,
    `Eaten: ${n0(intake.kcal)} kcal — P ${n0(intake.p)} g, C ${n0(intake.c)} g, F ${n0(intake.f)} g`,
    `Burned (est.): ${n0(burn.total)} kcal · Net: ${n0(intake.kcal - burn.total)} kcal`].filter(Boolean).join('\n');
}

const VIEWS = { today: viewToday, gym: viewGym, food: viewFood, report: viewReport };
function render({ still = false } = {}) {
  const view = $('#view'), keepText = $('#food-text')?.value;
  $('#top').innerHTML = topBar();
  view.classList.toggle('still', still);
  view.innerHTML = VIEWS[state.tab]();
  if (still && keepText && $('#food-text')) $('#food-text').value = keepText;
  $('#tabs').innerHTML = TABS.map(([k, l]) => `<button data-act="tab:${k}" ${state.tab === k ? 'aria-current="page"' : ''} aria-label="${l}">${ICON[k]}<span>${l}</span></button>`).join('');
  runAnims();
}

/* ---------- sheets ---------- */
function openSheet(html, { locked = false, fresh = true } = {}) {
  state.locked = locked;
  const root = $('#sheet-root');
  if (!fresh && $('.sheet', root)) { $('.sheet', root).innerHTML = html; return; }
  root.innerHTML = `<div class="scrim"><div class="sheet" role="dialog" aria-modal="true">${html}</div></div>`;
  $('.sheet [autofocus]', root)?.focus();
}
function closeSheet() {
  const scrim = $('.scrim'); if (!scrim) return;
  state.locked = false; state.pending = null; state.online = null;
  scrim.classList.add('closing');
  setTimeout(() => { if (scrim.isConnected) scrim.remove(); }, 220);
}

function profileForm(p, withTargets) {
  const t = p.targets, opt = (v, l, cur) => `<option value="${v}" ${cur === v ? 'selected' : ''}>${l}</option>`;
  const numIn = (name, val, label, extra = '') => `<label>${label}<input class="in num" name="${name}" inputmode="decimal" value="${esc(val)}" ${extra}></label>`;
  return `<form class="form" id="profile-form" novalidate>
    <div class="two"><label>Sex<select class="in" name="sex">${opt('male', 'Male', p.sex)}${opt('female', 'Female', p.sex)}</select></label>${numIn('age', p.age, 'Age')}</div>
    <div class="two">${numIn('heightCm', p.heightCm, 'Height (cm)')}${numIn('weightKg', p.weightKg, 'Weight (kg)')}</div>
    <label>Goal<select class="in" name="goal">${opt('cut', 'Lose fat', p.goal)}${opt('maintain', 'Maintain', p.goal)}${opt('bulk', 'Build muscle', p.goal)}</select></label>
    <div class="two">${numIn('stepGoal', p.stepGoal, 'Daily step goal')}${numIn('runMin', p.runMin, 'Morning run (min)')}</div>
    ${numIn('walkMin', p.walkMin, 'Morning walk (min)')}
    ${withTargets ? `<label class="row" style="grid-auto-flow:column;justify-content:start"><input type="checkbox" name="autoTargets" ${p.autoTargets ? 'checked' : ''} data-act-change="auto-targets"> Work out my calorie and macro targets for me</label>
    <div class="four">${numIn('kcal', t.kcal, 'kcal', p.autoTargets ? 'disabled' : '')}${numIn('protein', t.protein, 'Protein g', p.autoTargets ? 'disabled' : '')}${numIn('carbs', t.carbs, 'Carbs g', p.autoTargets ? 'disabled' : '')}${numIn('fat', t.fat, 'Fat g', p.autoTargets ? 'disabled' : '')}</div>` : ''}
  </form>`;
}

function sheetOnboard() {
  openSheet(`<h1>Set up Stride</h1><p class="sub">Used to estimate distance, calories burned and your daily targets. Stays on this device.</p>
    ${profileForm(profile(), false)}<div class="actions"><button class="btn" data-act="save-profile">Start tracking</button></div>`, { locked: true });
}
function sheetSettings() {
  openSheet(`<h1>Profile & targets</h1><p class="sub">Everything is stored on this device only.</p>${profileForm(profile(), true)}
    <div class="actions"><button class="btn ghost" data-act="close">Cancel</button><button class="btn" data-act="save-profile">Save</button></div>
    <p class="group">Your data</p>
    <div class="actions" style="margin-top:8px"><button class="btn ghost small" data-act="export">Export backup</button><button class="btn ghost small" data-act="import">Import backup</button><button class="btn danger small" data-act="reset">Erase all</button></div>
    <input type="file" id="import-file" accept="application/json,.json" hidden>`);
}
function sheetSteps() {
  openSheet(`<h1>Steps today</h1><p class="sub">Enter the total from Google Fit or your phone. Automatic sync arrives with the Android build.</p>
    <input id="steps-in" class="in big-in num" inputmode="numeric" value="${day().steps || ''}" placeholder="0" aria-label="Steps" autofocus>
    <div class="actions"><button class="btn ghost" data-act="close">Cancel</button><button class="btn" data-act="save-steps">Save</button></div>`);
}
function sheetExercises(q = '') {
  const ql = q.trim().toLowerCase();
  const groups = Object.entries(EXERCISES).map(([g, list]) => [g, list.filter((x) => x.toLowerCase().includes(ql))]).filter(([, l]) => l.length);
  const body = `${ql && !groups.some(([, l]) => l.some((x) => x.toLowerCase() === ql)) ? `<button class="pick" data-act="pick-ex" data-name="${esc(q.trim())}">Add “${esc(q.trim())}” <small>custom</small></button>` : ''}
    ${groups.map(([g, list]) => `<p class="group">${g}</p>${list.map((x) => `<button class="pick" data-act="pick-ex" data-name="${esc(x)}">${x}</button>`).join('')}`).join('')}`;
  if ($('#ex-list')) { $('#ex-list').innerHTML = body; return; }
  openSheet(`<h1>Add exercise</h1><input class="in" id="ex-search" data-in="ex-search" placeholder="Search or type your own" aria-label="Search exercises" style="margin-top:8px"><div id="ex-list">${body}</div>`);
}

function previewRow(r, i) {
  if (!r.food) return `<div class="prow"><div class="meta"><b style="color:var(--text)">${esc(r.raw)}</b><span class="miss">No match</span></div>
    <div class="row"><button class="btn ghost small" data-act="create-food:${i}">Enter macros</button><button class="btn ghost small" data-act="online:${i}">Search online</button></div></div>`;
  const m = C.itemMacros({ grams: r.grams, per: r.food.per });
  return `<div class="prow"><div class="line">
      <select class="in" data-change="pfood:${i}" aria-label="Food for ${esc(r.raw)}">${r.matches.map((f, j) => `<option value="${j}" ${f === r.food ? 'selected' : ''}>${esc(f.name)}${f.mine ? ' (yours)' : ''}</option>`).join('')}<option value="new">Something else…</option></select>
      <label class="set" style="display:block;margin:0;position:relative"><input class="in num" inputmode="decimal" data-in="pgrams:${i}" value="${r.grams}" aria-label="Grams"><em style="position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--faint);font-style:normal;font-size:12px">g</em></label></div>
    <div class="meta"><span>${esc(r.raw)} → ${esc(describe(r.qty, r.unit, r.food))}</span><span class="num" id="pm-${i}">${n0(m.kcal)} kcal · ${n1(m.p)} g P</span></div></div>`;
}
function sheetPreview(fresh = true) {
  const { rows, meal } = state.pending, ok = rows.filter((r) => r.food).length;
  openSheet(`<h1>Check before adding</h1><p class="sub">Amounts are estimates — adjust the grams if you know them.</p>
    ${rows.map(previewRow).join('')}
    <div class="actions"><button class="btn ghost" data-act="close">Cancel</button><button class="btn" data-act="confirm-food" ${ok ? '' : 'disabled'}>Add ${ok} to ${meal}</button></div>`, { fresh });
}
function sheetCreateFood(i) {
  const r = state.pending?.rows[i];
  openSheet(`<h1>New food</h1><p class="sub">Saved to your foods, so next time it matches by name.</p>
    <form class="form" id="food-form" data-row="${i ?? ''}" novalidate>
      <label>Name<input class="in" name="name" value="${esc(r ? r.name.replace(/^./, (c) => c.toUpperCase()) : '')}"></label>
      <div class="two"><label>One serving is called<input class="in" name="unit" value="${esc(r?.unit ?? 'serving')}"></label><label>Serving weight (g)<input class="in num" name="g" inputmode="decimal" value="100"></label></div>
      <p class="hint" style="margin:0">Macros for one serving:</p>
      <div class="four"><label>kcal<input class="in num" name="kcal" inputmode="decimal"></label><label>Protein<input class="in num" name="p" inputmode="decimal"></label><label>Carbs<input class="in num" name="c" inputmode="decimal"></label><label>Fat<input class="in num" name="f" inputmode="decimal"></label></div>
    </form><div class="actions"><button class="btn ghost" data-act="back-preview">Back</button><button class="btn" data-act="save-food">Save food</button></div>`, { fresh: false });
}
function sheetOnline() {
  const o = state.online, r = state.pending.rows[o.idx];
  const body = o.loading ? '<p class="hint">Searching Open Food Facts…</p>'
    : o.error ? `<p class="hint" style="color:var(--danger)">${esc(o.error)}</p>`
    : o.results.length ? o.results.map((x, j) => `<button class="pick" data-act="pick-online:${j}">${esc(x.name)}<small>${n0(x.per[0])} kcal · ${n1(x.per[1])} g P per 100 g</small></button>`).join('')
    : '<p class="hint">Nothing found. Packaged products work best here; for home food, enter the macros yourself.</p>';
  openSheet(`<h1>Online results</h1><p class="sub">“${esc(r.name)}” on Open Food Facts (free, community data).</p>${body}
    <div class="actions"><button class="btn ghost" data-act="back-preview">Back</button></div>`, { fresh: false });
}
async function searchOnline(idx) {
  const r = state.pending.rows[idx];
  state.online = { idx, loading: true }; sheetOnline();
  try {
    const url = `https://world.openfoodfacts.org/cgi/search.pl?search_terms=${encodeURIComponent(r.name)}&search_simple=1&action=process&json=1&page_size=8&fields=product_name,brands,nutriments,serving_quantity`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Open Food Facts answered ${res.status}`);
    const json = await res.json();
    const results = (json.products ?? []).map((x) => {
      const nt = x.nutriments ?? {}, kcal = +nt['energy-kcal_100g'];
      if (!x.product_name || !Number.isFinite(kcal)) return null;
      return { name: [x.product_name, x.brands?.split(',')[0]].filter(Boolean).join(' · '), unit: 'serving', g: +x.serving_quantity > 0 ? +x.serving_quantity : 100,
        per: [kcal, +nt.proteins_100g || 0, +nt.carbohydrates_100g || 0, +nt.fat_100g || 0] };
    }).filter(Boolean);
    if (state.online?.idx === idx) { state.online = { idx, results }; sheetOnline(); }
  } catch (err) {
    console.error('Stride: online food search failed', err);
    if (state.online?.idx === idx) { state.online = { idx, error: `Search failed (${err.message}). Check your connection, or enter the macros yourself.` }; sheetOnline(); }
  }
}
function useNewFood(food, idx) {
  store.data.myFoods = store.data.myFoods.filter((f) => f.name.toLowerCase() !== food.name.toLowerCase());
  store.data.myFoods.push(food); store.save();
  const r = state.pending?.rows[idx];
  if (!r) return;
  const mine = { ...food, aliases: [], aliasText: '', mine: true };
  r.food = mine; r.matches = [mine, ...r.matches]; r.grams = C.round(gramsFor(mine, r.qty, r.unit), 1);
  state.online = null; sheetPreview(false);
}
function sheetEditItem(meal, i) {
  const it = day().meals[meal][i]; if (!it) return;
  openSheet(`<h1>${esc(it.name)}</h1><p class="sub">${n0(it.per[0])} kcal · ${n1(it.per[1])} g protein per 100 g</p>
    <form class="form"><label>Amount eaten (g)<input id="item-g" class="in num" inputmode="decimal" value="${it.grams}" autofocus></label></form>
    <div class="actions"><button class="btn ghost" data-act="close">Cancel</button><button class="btn" data-act="save-item:${meal}:${i}">Save</button></div>`);
}

/* ---------- actions ---------- */
const posNum = (v) => { const x = parseFloat(v); return Number.isFinite(x) && x >= 0 ? x : null; };

const ACT = {
  tab(k) { state.tab = k; render(); window.scrollTo(0, 0); },
  day(n) { const next = +n === 0 ? todayKey() : shiftKey(state.date, +n); if (next > todayKey() || next === state.date) return; state.date = next; state.anim.clear(); render(); },
  goto(k) { state.date = k; state.anim.clear(); render(); },
  settings: sheetSettings, steps: sheetSteps, close: closeSheet,
  toggle(k) { const d = edit(); if (k === 'gym') d.gym.done = !d.gym.done; else d.checks[k] = !d.checks[k]; commit({ still: true }); },
  'save-steps'() {
    const v = posNum($('#steps-in').value || 0);
    if (v === null || v > 200000) return toast('Enter a step count between 0 and 200,000');
    edit().steps = Math.round(v); closeSheet(); commit({ still: true });
  },
  'save-profile'() {
    const f = new FormData($('#profile-form')), get = (k) => posNum(f.get(k));
    const p = { ...profile(), sex: f.get('sex'), goal: f.get('goal'), age: get('age'), heightCm: get('heightCm'), weightKg: get('weightKg'), stepGoal: get('stepGoal'), walkMin: get('walkMin'), runMin: get('runMin') };
    const bad = !(p.age >= 10 && p.age <= 100) ? 'age (10–100)' : !(p.heightCm >= 100 && p.heightCm <= 230) ? 'height (100–230 cm)' : !(p.weightKg >= 30 && p.weightKg <= 250) ? 'weight (30–250 kg)'
      : !(p.stepGoal >= 1000 && p.stepGoal <= 100000) ? 'step goal (1,000–100,000)' : p.walkMin === null || p.runMin === null ? 'walk and run minutes' : null;
    if (bad) return toast(`Check your ${bad}`);
    if ($('#profile-form [name=autoTargets]')) {
      p.autoTargets = f.get('autoTargets') === 'on';
      if (!p.autoTargets) {
        const t = { kcal: get('kcal'), protein: get('protein'), carbs: get('carbs'), fat: get('fat') };
        if (Object.values(t).some((v) => v === null) || t.kcal < 800) return toast('Check your targets — calories must be at least 800');
        p.targets = t;
      }
    }
    if (p.autoTargets) delete p.targets;
    store.data.profile = p; closeSheet(); commit(); toast('Saved');
  },
  intensity(v) { edit().gym.intensity = v; commit({ still: true }); },
  'gym-min'(n) { const g = edit().gym; g.minutes = Math.max(5, Math.min(240, g.minutes + +n)); commit({ still: true }); },
  'add-ex'() { sheetExercises(); },
  'pick-ex'() { edit().gym.exercises.push({ name: this.dataset.name, sets: [{ reps: '', kg: '' }] }); closeSheet(); commit({ still: true }); },
  'del-ex'(i) { edit().gym.exercises.splice(+i, 1); commit({ still: true }); },
  'add-set'(i) { const sets = edit().gym.exercises[+i].sets; sets.push({ ...(sets.at(-1) ?? { reps: '', kg: '' }) }); commit({ still: true }); },
  'del-set'(i, j) { const ex = edit().gym.exercises[+i]; ex.sets.splice(+j, 1); commit({ still: true }); },
  'repeat-last'() { const k = lastWorkoutKey(); if (!k) return; const src = store.data.days[k].gym; Object.assign(edit().gym, structuredClone({ exercises: src.exercises, intensity: src.intensity, minutes: src.minutes })); commit({ still: true }); toast('Copied your last workout'); },
  meal(k) { state.meal = k; render({ still: true }); },
  'add-food'() {
    const rows = resolveEntry($('#food-text').value, allFoods());
    if (!rows.length) return toast('Type what you ate first');
    state.pending = { meal: state.meal, rows }; sheetPreview();
  },
  'confirm-food'() {
    const { rows, meal } = state.pending, good = rows.filter((r) => r.food && r.grams > 0);
    edit().meals[meal].push(...good.map((r) => ({ name: r.food.name, label: describe(r.qty, r.unit, r.food), grams: r.grams, per: [...r.food.per] })));
    const skipped = rows.length - good.length;
    closeSheet(); if ($('#food-text')) $('#food-text').value = '';
    commit({ still: true }); toast(`Added ${good.length}${skipped ? ` · ${skipped} skipped` : ''}`);
  },
  'create-food'(i) { sheetCreateFood(+i); },
  'back-preview'() { state.online = null; sheetPreview(false); },
  online(i) { searchOnline(+i); },
  'pick-online'(j) { const o = state.online, x = o.results[+j]; useNewFood({ name: x.name, unit: x.unit, g: x.g, per: x.per.map((v) => C.round(v, 1)) }, o.idx); },
  'save-food'() {
    const form = $('#food-form'), f = new FormData(form), name = String(f.get('name')).trim(), g = posNum(f.get('g'));
    const vals = ['kcal', 'p', 'c', 'f'].map((k) => posNum(f.get(k) || 0));
    if (!name) return toast('Give the food a name');
    if (!g) return toast('Serving weight must be more than 0 g');
    if (vals.some((v) => v === null) || !posNum(f.get('kcal'))) return toast('Enter the calories for one serving');
    useNewFood({ name, unit: String(f.get('unit')).trim().toLowerCase() || 'serving', g, per: vals.map((v) => C.round((v / g) * 100, 1)) }, +form.dataset.row);
  },
  quick(i) { const it = state.recents?.[+i]; if (!it) return; edit().meals[state.meal].push(structuredClone(it)); commit({ still: true }); toast(`Added ${it.name}`); },
  'copy-meal'(k) { const y = store.data.days[shiftKey(state.date, -1)]; if (!y) return; edit().meals[k].push(...structuredClone(y.meals[k])); commit({ still: true }); },
  'del-item'(k, i) { edit().meals[k].splice(+i, 1); commit({ still: true }); },
  'edit-item'(k, i) { sheetEditItem(k, +i); },
  'save-item'(k, i) { const g = posNum($('#item-g').value); if (!g) return toast('Enter an amount above 0 g'); edit().meals[k][+i].grams = g; closeSheet(); commit({ still: true }); },
  async share() {
    const text = reportText();
    try { if (navigator.share) await navigator.share({ text }); else { await navigator.clipboard.writeText(text); toast('Report copied'); } }
    catch (err) { if (err.name !== 'AbortError') { console.error(err); toast('Could not share the report'); } }
  },
  export() {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(store.data)], { type: 'application/json' }));
    a.download = `stride-backup-${todayKey()}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  },
  import() { $('#import-file').click(); },
  reset() { if (!confirm('Erase all Stride data on this device? This cannot be undone.')) return; store.reset(); state.anim.clear(); closeSheet(); render(); sheetOnboard(); },
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (el) { const [name, ...args] = el.dataset.act.split(':'); ACT[name]?.call(el, ...args); return; }
  if (e.target.classList.contains('scrim') && !state.locked) closeSheet();
});

document.addEventListener('input', (e) => {
  const key = e.target.dataset?.in; if (!key) return;
  const [kind, a, b, field] = key.split(':');
  if (kind === 'set') {
    edit().gym.exercises[+a].sets[+b][field] = e.target.value.replace(/[^\d.]/g, '');
    store.save(); $('#gym-stats').textContent = gymStatsText(day(), profile());
  } else if (kind === 'pgrams') {
    const r = state.pending.rows[+a]; r.grams = posNum(e.target.value) ?? 0;
    const m = C.itemMacros({ grams: r.grams, per: r.food.per }); $(`#pm-${a}`).textContent = `${n0(m.kcal)} kcal · ${n1(m.p)} g P`;
  } else if (kind === 'ex-search') sheetExercises(e.target.value);
});

document.addEventListener('change', async (e) => {
  const t = e.target;
  if (t.dataset?.change?.startsWith('pfood:')) {
    const i = +t.dataset.change.split(':')[1], r = state.pending.rows[i];
    if (t.value === 'new') return sheetCreateFood(i);
    r.food = r.matches[+t.value]; r.grams = C.round(gramsFor(r.food, r.qty, r.unit), 1); sheetPreview(false);
  } else if (t.dataset?.actChange === 'auto-targets') {
    for (const k of ['kcal', 'protein', 'carbs', 'fat']) $(`#profile-form [name=${k}]`).disabled = t.checked;
  } else if (t.id === 'import-file' && t.files[0]) {
    try { store.replace(JSON.parse(await t.files[0].text())); state.anim.clear(); closeSheet(); render(); toast('Backup restored'); }
    catch (err) { console.error(err); toast(`Import failed: ${err.message}`); }
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !state.locked) closeSheet();
  if (e.key === 'Enter' && e.target.id === 'steps-in') ACT['save-steps']();
});
document.addEventListener('submit', (e) => e.preventDefault());
document.addEventListener('visibilitychange', () => { if (!document.hidden && !$('.scrim')) render({ still: true }); });

render();
if (!store.profile) sheetOnboard();
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch((err) => console.error('Stride: offline mode unavailable', err));
