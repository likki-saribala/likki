# Stride

A single-user daily tracker: steps and distance, morning walk/run, gym sets, typed food
with macros, and a daily report. Static files, no build step, data stays in the browser
(`localStorage`).

## Run it

```sh
cd stride
python3 -m http.server 8000   # open http://localhost:8000
npm test                      # unit tests (Node 20+, no dependencies)
```

## How numbers are calculated

All calorie figures are estimates.

| Number | Formula |
|---|---|
| Resting burn | Mifflin-St Jeor BMR |
| Distance | steps × height × 0.415 |
| Step calories | distance × body weight × 0.5 kcal/kg/km |
| Run | extra over walking: (8.3 − 3.5 MET) × kg × hours (its steps are already counted) |
| Gym | 2.5 / 4 / 5 net MET for light / moderate / intense × kg × hours |
| Food | bundled table of typical per-100 g values (`js/foods.js`), plus your own saved foods |

## Steps

In a browser the step count is typed in. The Android app in `../stride-android` reads it
from Health Connect through `js/native.js`.

Online food search (Open Food Facts) is wired in but has not been verified against the live service.

## Files

| Path | What it is |
|---|---|
| `js/calc.js` | Pure maths: burn, targets, macros, score, streak |
| `js/foodparse.js` | Turns "2 roti, 150g chicken" into matched foods and grams |
| `js/foods.js`, `js/exercises.js` | Bundled food table and exercise list |
| `js/store.js` | Storage |
| `js/native.js` | Bridge to the Android shell (step sync, share, backup) |
| `js/app.js` | Views, sheets and actions |
| `tests/` | Unit tests for the maths, parser and food table |
