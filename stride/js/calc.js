// Pure maths for Stride. No DOM, no storage — everything here is unit-tested.
// All calorie figures are estimates from standard formulas, not measurements.

export const RUN_MET = 8.3;   // ~8 km/h jog
export const WALK_MET = 3.5;  // brisk walk
// Net METs (resting already counted in BMR) for resistance training.
export const GYM_NET_MET = { light: 2.5, moderate: 4, intense: 5 };
export const NET_WALK_KCAL_PER_KG_KM = 0.5;

export const round = (n, d = 0) => { const m = 10 ** d; return Math.round((n + Number.EPSILON) * m) / m; };
const num = (v) => (Number.isFinite(+v) && +v > 0 ? +v : 0);

/** Mifflin-St Jeor resting energy, kcal/day. */
export function bmr(p) {
  const base = 10 * num(p.weightKg) + 6.25 * num(p.heightCm) - 5 * num(p.age);
  return Math.max(0, p.sex === 'female' ? base - 161 : base + 5);
}

export const strideM = (heightCm) => (num(heightCm) * 0.415) / 100;
export const stepsToKm = (steps, heightCm) => (num(steps) * strideM(heightCm)) / 1000;
export const stepsKcal = (steps, p) => stepsToKm(steps, p.heightCm) * num(p.weightKg) * NET_WALK_KCAL_PER_KG_KM;

/** Running steps are already in the step count at walking cost; this is only the extra. */
export const runExtraKcal = (min, kg) => ((RUN_MET - WALK_MET) * num(kg) * num(min)) / 60;
export const gymKcal = (min, intensity, kg) => ((GYM_NET_MET[intensity] ?? GYM_NET_MET.moderate) * num(kg) * num(min)) / 60;

export function dayBurn(day, p) {
  const rest = bmr(p);
  const steps = stepsKcal(day.steps, p);
  const run = day.checks.run ? runExtraKcal(p.runMin, p.weightKg) : 0;
  const gym = day.gym.done ? gymKcal(day.gym.minutes, day.gym.intensity, p.weightKg) : 0;
  const active = steps + run + gym;
  return { rest, steps, run, gym, active, total: rest + active };
}

/** Macros of one logged item: grams eaten × per-100 g values [kcal, p, c, f]. */
export function itemMacros(item) {
  const k = num(item.grams) / 100;
  const [kcal, p, c, f] = item.per;
  return { kcal: kcal * k, p: p * k, c: c * k, f: f * k };
}

export function sumMacros(items) {
  return items.reduce((t, it) => {
    const m = itemMacros(it);
    return { kcal: t.kcal + m.kcal, p: t.p + m.p, c: t.c + m.c, f: t.f + m.f };
  }, { kcal: 0, p: 0, c: 0, f: 0 });
}

export const dayItems = (day) => Object.values(day.meals).flat();
export const dayIntake = (day) => sumMacros(dayItems(day));

/** Daily targets from profile: planned burn adjusted for goal, protein by body weight. */
export function suggestTargets(p) {
  const planned = bmr(p) + stepsKcal(p.stepGoal, p) + runExtraKcal(p.runMin, p.weightKg) + gymKcal(60, 'moderate', p.weightKg);
  const factor = { cut: 0.8, maintain: 1, bulk: 1.1 }[p.goal] ?? 1;
  const kcal = Math.round((planned * factor) / 10) * 10;
  const protein = Math.round(num(p.weightKg) * (p.goal === 'cut' ? 2 : 1.8));
  const fat = Math.round((kcal * 0.25) / 9);
  const carbs = Math.max(0, Math.round((kcal - protein * 4 - fat * 9) / 4));
  return { kcal, protein, carbs, fat };
}

export function workoutStats(gym) {
  let sets = 0, volume = 0;
  for (const ex of gym.exercises) for (const s of ex.sets) {
    if (num(s.reps)) { sets += 1; volume += num(s.reps) * num(s.kg); }
  }
  return { exercises: gym.exercises.length, sets, volume };
}

/** 0–100: five equal parts — walk, run, steps (proportional), gym, diet. */
export function dayScore(day, p) {
  const stepPart = p.stepGoal > 0 ? Math.min(1, num(day.steps) / p.stepGoal) : 0;
  const parts = [day.checks.walk, day.checks.run, stepPart, day.gym.done, day.checks.diet];
  return Math.round(parts.reduce((s, v) => s + (v === true ? 1 : v || 0), 0) * 20);
}

/** Consecutive days scoring >= 80. An unfinished today doesn't break the streak. */
export function streak(days, p, fromKey, prevKey) {
  const ok = (k) => Boolean(days[k]) && dayScore(days[k], p) >= 80;
  let k = ok(fromKey) ? fromKey : prevKey(fromKey);
  let n = 0;
  while (ok(k) && n < 3650) { n += 1; k = prevKey(k); }
  return n;
}
