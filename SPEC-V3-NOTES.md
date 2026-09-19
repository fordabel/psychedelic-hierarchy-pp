# v3 rework — what changed, and where the spec and the repo disagreed

Written against `figure.html` as of this change. The previous version is kept
verbatim at `figure.v2.html.bak`.

## Where the spec and the repo disagreed

The spec was written from design discussion, not from the code. Six places
where it described something the repo did not contain, or described it
differently. In each case the repo won and the spec was adapted.

1. **"Panel B — the layered network, amended. Do not delete this panel."**
   There was no layered-network panel. Panel B was `Where this is in the
   brain`: four cortical-surface renders. Nothing in the repo, or in the v1
   project next door, had lattice geometry, an Ising reading, or an activation
   state. Rather than delete the surface panel — which the spec never asks for
   and which is the only thing tying the schematic to real cortex — the lattice
   was **built as a new Panel B**, and the surface renders became **Panel C**.

2. **"the existing T1w/T2w-derived connectivity"** — does not exist. T1w/T2w
   yields a per-parcel scalar (`level`, `myelin` in `parcels.json`), not a
   connectivity matrix, and the repo has no tractography and no functional
   connectivity; its own ledger said so. There is therefore no measured
   "structural connection strength" to sort recruitment by. What was built
   instead: each node's candidate targets are walked outward along the figure's
   own anatomical scaffold, tier by tier, and ordered by (tier, measured
   T1w/T2w level drop, angular proximity). That keeps fan-out dependent on each
   node's real topology, which is what the spec wanted the ordering for, and it
   is labelled as schematic on the figure.

3. **"Prior halos. Per-node halo width from `1/pi_i`."** The halo width came
   from `sigma_i = 1/sqrt(max(pi_i, 0.02))`, not `1/pi_i`. Same monotone
   function of the slider, so the removal stands.

4. **Panel A "modality-interpolated fill."** Node fill was Mesulam type only.
   A previous fix had deliberately demoted sensory stream out of the colour
   channel (it put a blue next to idiotypic blue) and moved it to the wedge
   arcs' dash pattern. Kept as the repo had it, so a node and its parcel are
   still the same hex in every panel.

5. **"the outer band lights in the visual wedge."** Not what the atlas says.
   In ring 0 the highest Cimbi-36 parcels are `PEF` and `6r` (somatomotor,
   94th/87th percentile) and `LBelt`/`A1` (auditory); `V1` is 55th. The lowest
   are also somatomotor — `4`, `3a`, `5m`, all below the 5th percentile. So the
   outer collar's angular structure is a *trough over M1/S1 and a peak over
   premotor and auditory*, not a visual peak.

6. **"dense in transmodal cortex (inner rings)."** Half true, and the half that
   is false is the more interesting one. Mean 5-HT2A percentile by ring:
   idiotypic 31, unimodal 52, **heteromodal 63**, **paralimbic 34**. Paralimbic
   is low because medial-temporal allocortex (`H`, `PreS`, `Pir`, `EC`) sits at
   the floor of the map, even while posterior cingulate (`d23ab`, `31pv`,
   `23d`) is in the global top ten. The ring readout therefore does *not* fall
   monotonically inward — it falls hardest in heteromodal — and the cascade
   gets stuck at heteromodal rather than reaching the apex. `FIG.censusRho()`
   prints the table.

One thing the spec did not mention that was broken: **`bundle_standalone.py`
could not run.** Its `IMGS` list named `brain_nodes` (never produced) and
omitted `brain_ids` (added to the page when per-parcel hover landed), so every
bundle attempt died on an unreplaced asset reference. Both bundles on disk were
a day older than `figure.html`. Fixed, and `brain_ids.png` is now inlined
byte-exact — it is a pixel→parcel lookup table, and quantising it would have
silently killed hover.

## Removals — all done

`disruption bars` (`rho_percentile × (1 − pi)`), `prior halos`, the four
`generative model` distribution cards, `penetration depth` as a named headline,
and the `MEASURED / DERIVED / ASSUMED` three-tier badge scheme are gone, along
with their toggles, their equations and their entries in the ledger.

Two further removals the spec implies but does not name:

- **The ambient ascending-error field.** `E[i] = e_in · (1 − pi_i)` propagated
  inward was a fourth deterministic restatement of the slider. The ascending
  channel is now the anatomy only — one thin inward arrow per radial scaffold
  link, constant at every slider position — and what happens to a particular
  error at a particular precision is the cascade, which you click.
- **`rho = 0` for parcels with no PET signal.** Two parcels (`L_H`, `R_H`)
  carry `rhoValid=false` and were silently being treated as density zero, which
  meant they never relaxed and dragged the paralimbic mean down. They now make
  no receptor claim at all: gap in the collar, hollow node, a slash in the
  lattice cell, excluded from the ring readout.

## What replaced them

**Precision lives on edges.** Each node has an ordered candidate list; the
slider sets how far down it reaches, gated by receptor percentile:

    d_i   = (1 − pi)^GAMMA · rho_i            drug strength at node i
    k_i   = K0 + KGAIN · d_i                  targets recruited (continuous)
    w_ij  = (1 + WGAIN · d_i) · p_ij          per-target weight
    conc_i = 1 / exp(H(p_i))                  concentration of the drawn vector
    index_i = conc_i / conc_i(pi = 100)

Descending edges are never faded and never culled — fading them is the reading
of REBUS its critics object to. They **proliferate**: 650 edges at pi = 100,
2203 at pi = 0; total drive rises ×1.30; mean weight per target falls 0.40 →
0.15. `FIG.assertProliferation()` fails loudly at load if either of those ever
goes the wrong way.

**Headline.** Four numbers, one per ring, on one shared axis so the *fanning*
is the visual event. `1.00 1.00 1.00 1.00` at pi = 100 → `0.56 0.44 0.37 0.58`
at pi = 0. Note the order: heteromodal collapses furthest, idiotypic and
paralimbic least. That is the receptor map, not the ring index.

**Receptor collar.** Four concentric arc tracks, one per ring, in the gutter
inside each node orbit, one segment per parcel at that parcel's own angular
slot. Coloured by percentile — the colourbar prints BP_ND at the deciles —
because the measured spread is narrow enough that a linear encoding reads as
one flat colour on a projector. Drawn *over* the traffic: at low precision two
thousand edges cross that gutter.

**Panel B.** The same parcels unrolled: row = Mesulam ring, column = gradient
rank, 36 columns. Within-level coupling is constant. Across-level coupling is
`VGAIN · (1 − index)` of the upper cell, so it is **exactly zero at pi = 100**
and every patch is sealed inside its layer. Patches are components joined by
*open bonds*, not merely adjacent cells — that distinction is what stops four
stacked row-patches from reading as one spanning patch. Across the slider:
33% active / span 1 level → 67% active / span 4, with the first breakthrough at
pi ≈ 65 and no saturation at the bottom. Seeds are a fixed comb, identical in
every row, so a uniform probe makes an uneven response legible.

**Cascade.** Deterministic, no sampling. `e_y = e_x · CGAIN · p(y→x)^CSHARE ·
(1 − index_y)`, propagating along the reciprocal of the descending map — so the
ascending fan-out is not a second assumption, it is the drawn structure
reversed. At pi = 100 the index is 1, the factor is 0, and the error is
explained away where it lands. 3–4 s for a full run, one generation per beat,
space pauses, esc clears. Moving the slider **re-traces the cascade live** in
both panels instead of leaving a stale trace on screen.

**Generation ladder.** One row per hop, one mark per parcel, coloured by level;
the row after the last one is drawn as a real empty row reading `— nothing`.
Empty at rest. The freeze-frame triptych (`Freeze-frame` button, kept out of
the hidden-in-presentation chip row on purpose) shows the same node at pi =
85 / 55 / 15 side by side: `dies out` (1,3) / `holds` (1,3,9) / `spreads`
(1,3,9,10,11).

**Labelling.** Two parts. Four inputs with source lines; one dynamics sentence,
painted onto the Panel A canvas as well as into the page, so it survives the
image being cropped out of the slide.

## Non-goals, held

No log-log panel, no power-law fit, no avalanche-size distribution, no
measurement axes anywhere. No stochastic sampling in the render path — the only
RNG in the file was deleted with the off-anatomy edge pool. No new quantitative
headline beyond the four-value row; the lattice and ladder captions are
descriptive counts of what is drawn.

## Console

`FIG.assertDirection()`, `FIG.assertProliferation()`, `FIG.ladders(step)`,
`FIG.censusRho()`, `FIG.censusWedge()`, `FIG.triptych()`, `FIG.state()`.
Every constant is in `FIG.P` and can be swept live; the tuning above was done
that way rather than by eye.

## Known stale

`assets/sources.json` still carries a `disruption` entry describing the removed
bars. Nothing renders it any more — the figure only reads that file to detect
whether tau is measured — but regenerating it means re-running `build_assets.py`,
which needs network access and the neuroimaging stack, so it was left alone.
