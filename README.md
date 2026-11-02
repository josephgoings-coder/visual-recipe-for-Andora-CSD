# Visual recipes

Illustrated flowchart versions of recipes. Each step card pairs a drawing with the
step's real detail: quantities, heat level, timings and the visual or doneness cue.

## Ànec amb Peres (Catalan duck with pears)

![Ànec amb Peres visual recipe](anec-amb-peres/anec-amb-peres-flowchart.png)

| File | What it is |
| --- | --- |
| `anec-amb-peres/anec-amb-peres-flowchart.png` | Rendered poster (2400 px wide) |
| `anec-amb-peres/flowchart.html` | Source: HTML/CSS layout with inline SVG illustrations |

Layout:

- **What you need**: ingredients grouped by component (duck, sofregit & braise,
  pears, picada), each tagged with the steps that use it, plus equipment and a prep list.
- **How to make it**: eight step cards linked by arrows. Steps 5 and 6 run in
  parallel while the legs braise (step 4), then all three merge into step 7.
- **Good to know**: swaps and make-ahead notes from the chef's tips.

Source recipe: “Ànec amb Peres” by Chef Isabel, Culinary Explorer.

## Re-rendering the PNG

Edit `flowchart.html`, then run:

```sh
node tools/render.js anec-amb-peres/flowchart.html anec-amb-peres/anec-amb-peres-flowchart.png
```

This needs Node and Playwright with Chromium. An optional third argument sets the
pixel scale (default `2`).

## Fonts

Fredoka and Patrick Hand, bundled in `assets/fonts/` under the SIL Open Font License 1.1.

## Människokroppen (Swedish anatomy posters)

Four language-learning posters labelling human anatomy in Swedish. Each label shows the
indefinite singular with its article, colour-coded by gender (**en** blue, **ett** orange).
All four are 3:5 (2160 × 3600 px).

| Poster | File |
| --- | --- |
| 1/4 Kroppens delar (body parts) | `anatomi/png/1-kroppens-delar.png` |
| 2/4 Inre organ (internal organs) | `anatomi/png/2-inre-organ.png` |
| 3/4 Muskler (muscles) | `anatomi/png/3-muskler.png` |
| 4/4 Skelettet (skeleton) | `anatomi/png/4-skelettet.png` |

Sources per category in `anatomi/<kroppen|organ|muskler|skelett>/`:

- `source.png`: the original English-labelled illustration
- `clean.py` → `clean.png`: removes the English labels, leader lines and dots
- `kroppen/skin.py` → `skin.png` (body parts only): repaints the figure as plain skin, without
  the organs, bones and vessels of the original, keeping the same pose so the label anchors still fit
- `poster.html`: label data (`window.POSTER`) for the shared template in `anatomi/shared/`

Re-render one poster (add `?grid` to the HTML path for a coordinate overlay; layout
problems are printed as warnings):

```sh
node tools/render.js anatomi/organ/poster.html anatomi/png/2-inre-organ.png 2
```
