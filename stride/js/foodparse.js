// Turns typed text ("2 roti, 1 katori dal, 150g chicken") into matched foods with gram amounts.
// Pure: no DOM, no storage.

const WORD_NUM = { a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, half: 0.5, quarter: 0.25 };
// Generic gram weights when the food has no specific serving for that unit.
export const UNIT_GRAMS = { g: 1, kg: 1000, ml: 1, l: 1000, katori: 150, bowl: 250, cup: 200, glass: 250, plate: 250, tbsp: 15, tsp: 5, scoop: 30 };
const UNIT_ALIASES = {
  g: 'g', gm: 'g', gms: 'g', gram: 'g', grams: 'g', kg: 'kg', kgs: 'kg', ml: 'ml', l: 'l', litre: 'l', liter: 'l',
  katori: 'katori', katoris: 'katori', bowl: 'bowl', bowls: 'bowl', cup: 'cup', cups: 'cup', glass: 'glass', glasses: 'glass',
  plate: 'plate', plates: 'plate', tbsp: 'tbsp', tablespoon: 'tbsp', tablespoons: 'tbsp', tsp: 'tsp', teaspoon: 'tsp', teaspoons: 'tsp',
  spoon: 'tsp', spoons: 'tsp', scoop: 'scoop', scoops: 'scoop', piece: 'piece', pieces: 'piece', pc: 'piece', pcs: 'piece',
  slice: 'slice', slices: 'slice', serving: 'serving', servings: 'serving', pack: 'pack', packs: 'pack', packet: 'pack',
};

const norm = (s) => s.toLowerCase().replace(/[^a-z0-9./ ]+/g, ' ').replace(/\s+/g, ' ').trim();
const singular = (w) => (w.length > 3 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w);

function readQty(tok) {
  if (tok in WORD_NUM) return WORD_NUM[tok];
  let m = tok.match(/^(\d+)\/(\d+)$/);
  if (m && +m[2]) return +m[1] / +m[2];
  m = tok.match(/^\d*\.?\d+$/);
  return m ? parseFloat(tok) : null;
}

/** "2 roti, 150g chicken and dal" -> [{raw, qty, unit, name}] */
export function parseEntry(text) {
  return String(text).split(/[,;\n+]|\band\b|\bwith\b/i).map((part) => {
    const raw = part.trim();
    // split "150g" / "2.5kg" into number + unit
    let toks = norm(raw).replace(/(\d)([a-z])/g, '$1 $2').split(' ').filter(Boolean);
    if (!toks.length) return null;
    let qty = null, unit = null;
    const take = (i) => {
      const q = readQty(toks[i]);
      if (q === null) return false;
      const u = UNIT_ALIASES[toks[i + 1]];
      qty = q; unit = u ?? null;
      toks.splice(i, u ? 2 : 1);
      return true;
    };
    // quantity first ("2 roti"), or last ("chicken 150 g")
    if (!take(0)) {
      const n = toks.length;
      if (n >= 3 && readQty(toks[n - 2]) !== null && UNIT_ALIASES[toks[n - 1]]) take(n - 2);
      else if (n >= 2 && readQty(toks[n - 1]) !== null) take(n - 1);
    }
    if (toks[0] === 'of') toks.shift();
    const name = toks.join(' ');
    return name ? { raw, qty: qty ?? 1, unit, name } : null;
  }).filter(Boolean);
}

function score(food, q, qToks) {
  const name = food.name.toLowerCase();
  if (name === q) return 100;
  const aliasFull = (food.aliasPhrases ??= [name, ...splitAliases(food)]);
  if (aliasFull.includes(q)) return 95;
  const words = (food.words ??= new Set([...name.split(' '), ...food.aliases].map(singular)));
  const hits = qToks.filter((t) => words.has(t)).length;
  if (hits === qToks.length) return 80 - Math.abs(name.split(' ').length - qToks.length) * 4 + (name.startsWith(qToks[0]) ? 3 : 0);
  if (hits) return 30 + (hits / qToks.length) * 30;
  if (qToks.some((t) => t.length >= 4 && [...words].some((w) => w.startsWith(t) || t.startsWith(w) && w.length >= 4))) return 25;
  return 0;
}
// Aliases are stored space-separated; multi-word aliases are recovered by matching the query as a substring.
function splitAliases(food) { return food.aliasText ? [food.aliasText] : []; }

/** Best matches for a typed name, user foods ranked above bundled ones on ties. */
export function searchFoods(query, foods, limit = 5) {
  const q = norm(query).split(' ').map(singular).join(' ');
  if (!q) return [];
  const qToks = q.split(' ');
  return foods
    .map((food, i) => {
      let s = score(food, q, qToks);
      if (s < 95 && food.aliasText && (' ' + food.aliasText + ' ').includes(' ' + q + ' ')) s = Math.max(s, 90);
      return { food, s: s + (food.mine ? 1 : 0), i };
    })
    .filter((r) => r.s >= 25)
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .slice(0, limit)
    .map((r) => r.food);
}

/** Grams for qty × unit of a food. Uses the food's own serving when the unit matches or is absent. */
export function gramsFor(food, qty, unit) {
  if (!unit || unit === food.unit) return qty * food.g;
  if (unit in UNIT_GRAMS) return qty * UNIT_GRAMS[unit];
  return qty * food.g; // piece / slice / serving / pack -> the food's serving
}

export function describe(qty, unit, food) {
  const u = unit ?? food.unit;
  const q = Math.round(qty * 100) / 100;
  if (u === 'g' || u === 'ml') return `${q} ${u}`;
  if (/^\d/.test(u)) return q === 1 ? u : `${q} × ${u}`;
  return `${q} ${u}`;
}

/** Parse + match in one go. Unmatched rows come back with food: null. */
export function resolveEntry(text, foods) {
  return parseEntry(text).map((e) => {
    const matches = searchFoods(e.name, foods);
    const food = matches[0] ?? null;
    return { ...e, matches, food, grams: food ? Math.round(gramsFor(food, e.qty, e.unit) * 10) / 10 : 0 };
  });
}
