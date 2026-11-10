import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as C from '../js/calc.js';
import { FOODS } from '../js/foods.js';
import { parseEntry, resolveEntry, searchFoods, gramsFor } from '../js/foodparse.js';

const P = { sex: 'male', age: 25, heightCm: 175, weightKg: 70, goal: 'maintain', stepGoal: 10000, walkMin: 30, runMin: 30 };
const day = (o = {}) => ({ steps: 0, checks: { walk: false, run: false, diet: false }, gym: { done: false, minutes: 60, intensity: 'moderate', exercises: [] }, meals: { breakfast: [], lunch: [], snacks: [], dinner: [] }, ...o });

test('BMR (Mifflin-St Jeor)', () => {
  assert.equal(C.bmr(P), 1673.75);
  assert.equal(C.bmr({ ...P, sex: 'female' }), 1507.75);
});

test('steps -> distance and calories', () => {
  assert.equal(C.round(C.stepsToKm(10000, 175), 2), 7.26);
  assert.equal(Math.round(C.stepsKcal(10000, P)), 254);
  assert.equal(C.stepsKcal(0, P), 0);
  assert.equal(C.stepsKcal('abc', P), 0);
});

test('gym calories scale with intensity', () => {
  assert.equal(C.gymKcal(60, 'light', 70), 175);
  assert.equal(C.gymKcal(60, 'moderate', 70), 280);
  assert.equal(C.gymKcal(60, 'intense', 70), 350);
  assert.equal(C.gymKcal(30, 'intense', 70), 175);
});

test('day burn only counts ticked activities', () => {
  const none = C.dayBurn(day({ steps: 10000 }), P);
  assert.equal(none.run, 0); assert.equal(none.gym, 0);
  const d = day({ steps: 10000, checks: { walk: true, run: true, diet: false } });
  d.gym.done = true;
  const b = C.dayBurn(d, P);
  assert.equal(Math.round(b.run), 168); assert.equal(b.gym, 280);
  assert.equal(Math.round(b.total), Math.round(1673.75 + 254.19 + 168 + 280));
});

test('targets: macros add up to the calorie target', () => {
  for (const goal of ['cut', 'maintain', 'bulk']) {
    const t = C.suggestTargets({ ...P, goal });
    assert.ok(Math.abs(t.protein * 4 + t.carbs * 4 + t.fat * 9 - t.kcal) <= 8, goal);
  }
  assert.ok(C.suggestTargets({ ...P, goal: 'cut' }).kcal < C.suggestTargets(P).kcal);
  assert.equal(C.suggestTargets(P).protein, 126);
});

test('item macros and totals', () => {
  const items = [{ grams: 80, per: [264, 8.5, 50, 3.5] }, { grams: 150, per: [105, 6, 15, 2.5] }];
  const t = C.sumMacros(items);
  assert.equal(C.round(t.kcal, 1), 368.7);
  assert.equal(C.round(t.p, 1), 15.8);
});

test('workout stats ignore empty sets', () => {
  const s = C.workoutStats({ exercises: [{ name: 'Bench', sets: [{ reps: 10, kg: 60 }, { reps: 8, kg: 65 }, { reps: '', kg: '' }] }] });
  assert.deepEqual(s, { exercises: 1, sets: 2, volume: 1120 });
});

test('day score and streak', () => {
  const full = day({ steps: 12000, checks: { walk: true, run: true, diet: true } }); full.gym.done = true;
  assert.equal(C.dayScore(full, P), 100);
  assert.equal(C.dayScore(day({ steps: 5000 }), P), 10);
  const prev = (k) => String(+k - 1);
  assert.equal(C.streak({ 5: day(), 4: full, 3: full, 2: day(), 1: full }, P, '5', prev), 2);
  assert.equal(C.streak({ 5: full, 4: full }, P, '5', prev), 2);
  assert.equal(C.streak({}, P, '5', prev), 0);
});

test('parser: quantities, units, positions', () => {
  assert.deepEqual(parseEntry('2 roti, 1 katori dal and 150g chicken breast'), [
    { raw: '2 roti', qty: 2, unit: null, name: 'roti' },
    { raw: '1 katori dal', qty: 1, unit: 'katori', name: 'dal' },
    { raw: '150g chicken breast', qty: 150, unit: 'g', name: 'chicken breast' },
  ]);
  assert.deepEqual(parseEntry('paneer 100 g')[0], { raw: 'paneer 100 g', qty: 100, unit: 'g', name: 'paneer' });
  assert.equal(parseEntry('half cup of oats')[0].qty, 0.5);
  assert.equal(parseEntry('1/2 plate poha')[0].qty, 0.5);
  assert.equal(parseEntry('banana')[0].qty, 1);
  assert.deepEqual(parseEntry(' , ,'), []);
});

test('matching: names, aliases, plurals, grams', () => {
  const top = (q) => searchFoods(q, FOODS)[0]?.name;
  assert.equal(top('chapati'), 'Roti');
  assert.equal(top('eggs'), 'Boiled egg');
  assert.equal(top('egg whites'), 'Egg white');
  assert.equal(top('chicken'), 'Chicken breast');
  assert.equal(top('chicken curry'), 'Chicken curry');
  assert.equal(top('whey'), 'Whey protein');
  assert.equal(top('rice'), 'Rice');
  assert.equal(top('curd'), 'Curd');
  assert.equal(top('xyzzy'), undefined);
  const r = resolveEntry('3 eggs, 200g rice, 1 scoop whey, 2 tsp ghee', FOODS);
  assert.deepEqual(r.map((x) => x.grams), [150, 200, 30, 10]);
  const mine = { name: 'Rice', aliases: [], aliasText: '', unit: 'bowl', g: 220, per: [130, 2.7, 28, 0.3], mine: true };
  assert.equal(searchFoods('rice', [...FOODS, mine])[0].mine, true);
  assert.equal(gramsFor(FOODS.find((f) => f.name === 'Roti'), 2, 'piece'), 80);
});

test('food table is sane: macros roughly explain calories', () => {
  for (const f of FOODS) {
    const [kcal, p, c, fat] = f.per;
    const est = p * 4 + c * 4 + fat * 9;
    assert.ok(Math.abs(est - kcal) <= Math.max(25, kcal * 0.2), `${f.name}: ${kcal} vs ${Math.round(est)}`);
    assert.ok(f.g > 0);
  }
  assert.equal(new Set(FOODS.map((f) => f.name)).size, FOODS.length);
});
