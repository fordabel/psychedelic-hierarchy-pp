# Figure body plan

The standing constraints, rules and goals for `figure.html`. This is the document
that governs the build. `SPEC-V3-NOTES.md` is a changelog for one iteration and
does not outrank this file. When this file and the code disagree, that is a bug
in one of them and the disagreement gets resolved, not tolerated.

Status tags used below: **[settled]** decided and stable · **[open]** needs a
decision before it is built · **[built]** agreed in the v4 discussion and now in
`figure.html`.

## v4 — what shipped

Panel A's canvas went from 930x600 to 1180x1040 and the ring's outer radius from
164 to 310 (1.9x linear, 3.5x area); the aspect was chosen so the canvas fits its
panel by width and by height at almost the same scale, which is where the old
dead band at the bottom came from. The receptor collar is gone and 5-HT2A is the
width of a `#6d1119` border on each node. Nodes flash: Kuramoto phase
oscillators, natural frequency from the measured timescale, coupling gated by the
node's own precision index and noise gated by its inverse. A perturbation can be
released from any node, upward as error or downward as prediction. Panel B is a
ball-and-edge network with within-level arcs and sparse irregular across-level
edges including diagonals, sized by its own control. Panel C's brain renders
(it was drawing at 0px) and the ledger moved to an overlay. sigma and the
percolation threshold are on the page, and the figure opens at the threshold.

Four constants were **solved rather than eyeballed**, and the derivation is in the
code comment beside each: `LAT0`/`LAT1` against the max-plus reach at 12 columns,
`ARCW` so the skip bond sits just below threshold at pi = 100, and `FLASH_KG`
against the locking threshold for the tau-derived frequency spread. A linear
`idx` gate on the coupling never took any level below Kc, so every ring stayed
synchronised and the desynchronisation channel carried nothing; that is the kind
of thing the spec exists to catch, and it was caught by measuring the sweep
rather than by looking at one frame.

Measured sweep, 100 -> 0: lattice 25% -> 81% active, tallest patch 1 -> 4 levels,
across-level bonds 0/48 -> 34/48, sigma 0.00 -> 0.95, mean phase coherence
0.99 -> 0.44 with heteromodal falling hardest (0.98 -> 0.20).

---

## 0. The claim

> Cortical 5-HT2A density indexes **where** descending prediction precision
> relaxes first. Relaxing it changes **where activity can travel**, and the
> change is not uniform across the cortical hierarchy.

Everything in the figure exists to make that sentence visible and falsifiable.
If an element does not serve it, the element is wrong, however pretty it is.

Corollary that keeps getting lost: the interesting result is **non-monotonicity**.
Mean 5-HT2A percentile by ring is idiotypic 31, unimodal 52, **heteromodal 63**,
paralimbic 34. The relaxation does *not* fall cleanly inward. Any design that
implies a smooth surface-to-apex gradient is misrepresenting the data.

---

## 1. Standing rules

These hold in every panel, at every slider position, forever.

**R1 — One channel, one meaning.** Each visual channel carries exactly one
variable across the whole figure. A channel is never re-used for a second
meaning in another panel. Current assignments:

| channel | carries |
|---|---|
| node fill | Mesulam cortical type (4 categories) |
| node radius | intrinsic timescale τ |
| node border width | 5-HT2A percentile ρ **[built]** |
| angular / column position | Margulies principal gradient rank |
| ring / row | Mesulam cortical type |
| edge width | that target's share of the source's descending drive |
| edge direction | measured T1w/T2w level drop |
| flash phase | within-level synchrony **[built]** |
| flash interval regularity | entropy **[built]** |

**R2 — One idea, one home.** Every claim is argued in exactly one panel. A panel
may *echo* another panel's state (a running cascade lights the same parcels in
both geometries) but never restates its argument.

**R3 — Colour identity is load-bearing.** A parcel is the same hex in A, B and C.
No panel may introduce a second colour encoding of level. This is why the
reference-image purple→gold ramp is not adopted: its geometry is the target, its
palette is not.

**R4 — Measured and schematic are always distinguishable.** Four inputs are
measured (§2). Everything else — ring radii, the anatomical scaffold, recruitment
order, the cascade rule, lattice couplings — is schematic and says so on the
figure, not only in the caption.

**R5 — Nothing is fitted.** No constant in `P` was tuned against data. They are
hand-picked so the slider sweep shows the transition the mechanism claims. This
is a teaching illustration of a mechanism, not a model of a drug effect.

**R6 — Direction is measured, not assumed.** Where T1w/T2w disagrees with the
Mesulam order the edge keeps its measured direction and is drawn as a visible
inversion (currently 148 of 680 cross-level edges). Inversions are never quietly
reversed to tidy the picture.

**R7 — Simulation is allowed; single draws are not claims. [built]**
Stochastic simulation is back on, in all panels. RNG may drive anything the eye
sees: flash timing and phase, avalanche seeding, lattice updates. Any **number
printed on the figure** must be either (a) measured, or (b) an ensemble statistic
over a stated number of runs from a stated seed. No printed number ever comes
from one random draw. Seeds are fixed so the figure is reproducible frame for
frame; the RNG buys realism, not irreproducibility.

**R8 — Descending edges are never faded or culled.** Under relaxation they
*proliferate*: more targets, each weaker, total drive up. Fading them is the
reading of REBUS its critics object to and the figure must not make it.
`FIG.assertProliferation()` fails loudly at load if this ever inverts.

**R9 — No element may require the caption to be legible.** The caption adds
provenance; it never supplies the meaning of a mark.

**R10 — Never overwrite `figure.html` without snapshotting it first.** Before any
edit session that changes the figure, copy the current file to
`figure.v<N>.html.bak`. The chain is the project's undo history and there is no
other one: this folder is not a git repository, and the bundles are regenerated
from whatever `figure.html` happens to be in place, so an overwrite with no
snapshot is unrecoverable. Current chain:

    figure.v2.html.bak   pre-collar
    figure.v3.html.bak   collar, no flashing, ring-0-only cascade
    figure.html          v4

(Initialising a git repo here would replace this rule with something better --
every intermediate state, real diffs, no filename discipline. Not done, because
it changes how the project is handled and that is the author's call.)

---

## 2. Measured inputs

Only these four are data. Everything else is scaffold.

| symbol | input | source | drives |
|---|---|---|---|
| ρ | cortical 5-HT2A density | Beliveau et al. 2017, [11C]Cimbi-36 BP_ND, parcel means | node border width; recruitment gating |
| τ | intrinsic timescale | MEG time constants, HCP S1200 (neuromaps hcps1200/megtimescale) | node radius (fixed; does not move with the slider) |
| — | edge direction | HCP S1200 group myelin map, inverted T1w/T2w | which way a prediction runs |
| — | parcellation | HCP-MMP1, 360 areas (Glasser 2016); ring = Mesulam type (Paquola 2019); angle/column = Margulies 2016 gradient |

Ring sizes are very unequal and every design must survive that: **idiotypic 44,
unimodal 121, heteromodal 127, paralimbic 68**. `downsample()` is stratified by
(ring x modality) and preserves the ratio at every node count, so no total ever
yields tidy equal rows.

**Geometry constants are not yet in `P`.** `RADII`, `SQUASH`, `CONTRACT`, `CX`,
`CY`, `RX`, `RW`, `ARC_R`, `LAB_R` are module-level consts, which contradicts the
§8 claim that every constant is sweepable live. Moving them into `P` is part of
the Panel A resize.

ρ is encoded by **percentile, not raw value**, everywhere. The measured BP_ND
spread is narrow enough that a linear encoding reads as one flat colour — and,
for the same reason, as one flat border width. The colourbar prints BP_ND at the
deciles so the compression is disclosed rather than hidden.

Two parcels (`L_H`, `R_H`) carry `rhoValid=false`: no cortical-ribbon PET signal.
They make **no receptor claim at all** — not density zero. They are drawn with a
distinct no-claim mark (not a thin border, which would read as "low"), never
recruit, and are excluded from the ring readout.

---

## 3. Panels

### Panel A — the sensory-fugal hierarchy

**Job:** show the two channels on real cortical topology, and let one perturbation
be released into it.

- Concentric rings, apex at centre, idiotypic outermost. Angle = gradient rank.
  Rings 0–1 share angular sectors so a sensory stream reads as a radial slice.
- **Size: the ring is the panel's subject and must dominate it. [built]** The
  binding constant is `RADII=[164,125,87,48]` inside a 930x600 canvas whose left
  half is all the ring gets: `CX=243`, readout column at `RX=452`, ~250px of dead
  space below. The readout text moves out of the canvas; `RADII` scales up and the
  ring re-centres. `SQUASH=0.98` is a 2% ovalization and is *not* the problem --
  it stays as it is.
- **Receptor lives on the node border, not in a collar. [built]** Border width ∝ ρ
  percentile. The collar's four arc tracks are removed, which also frees the
  gutter that two thousand edges cross at low precision.
- **Nodes flash. [built]** Phase carries within-level synchrony; interval regularity
  carries entropy. See §4.
- **A cascade may be released from any node. [built]** The current `ring===0` gate
  is a code restriction, not a finding, and it hides the most interesting case:
  heteromodal has the highest mean receptor percentile of the four rings.
- **Descending predictions propagate as an event, not only as a field. [built]**
  REBUS is a claim about the descending channel; animating only the ascending
  one puts the drama on the wrong arrow.

**Must not:** cull or fade descending edges (R8); imply a smooth inward gradient;
encode ρ in fill (it collides with idiotypic blue and breaks R3).

### Panel B — the lattice as a network

**Job:** the phase transition. Where activity stops being local.

- **Ball-and-edge, not stacked bars. [built]** Target aesthetic: circles, lateral
  arcs drawn *above* each row skipping a neighbour (i → i+2, overlapping), a
  straight adjacency line through the row, and **sparse irregular inter-level
  edges including crossing diagonals**. The diagonals are what break the
  stacked-rectangle read — circles alone do not.
- **Lattice geometry is kept, not force-directed.** Percolation on a lattice is
  the canonical criticality picture and is already what this panel computes; a
  force-directed blob destroys the "this patch spans N levels" readout. Positions
  may be jittered a few px off the grid to read organic.
- **Panel B gets its own width control, nested inside Panel A's. [built]** The two
  panels want opposite densities: A is a topology picture where density is part of
  the message (200-360 nodes), B is a mechanism picture that must be countable
  (10-14 per row). One control cannot serve both, which is why `COLS=36` has been
  papering over the gap by resampling every row to 36 slots -- duplicating parcels
  whenever a row holds fewer than 36.
  - `ncount` (Panel A): **140 / 200 / 260 / 360**.
  - `COLS` (Panel B): **8 / 12 / 16, default 12**, sampled evenly along the
    gradient *from whatever set A is currently showing*, so B's parcels are always
    a subset of A's and hover, echo and cascade-lighting stay coherent. Every ball
    remains a real parcel; nothing is binned or averaged.
  - **Hard guard:** `COLS` <= the smallest row count in A's subsample, or the
    duplication returns. That ceiling is 17 at A=140 and 31 at A=260.
  - **Disclosed cost:** equal rows misrepresent the census. The rings hold
    44/121/127/68 parcels, so 12 per row samples idiotypic at 27% and heteromodal
    at 9%. Accepted here because B's job is the phase transition and its fixed seed
    comb exists so that *a uniform probe makes an uneven response legible* -- a
    uniform probe wants uniform rows. The census lives in Panel C. The per-row
    sampling rate is stated on the panel, not hidden.
  - **Rejected alternative:** equal rows with ball size proportional to parcels
    represented. More honest about the census, but radius already means tau
    figure-wide, and a second meaning for that channel is precisely what R1
    forbids.
- **Structure and state are drawn separately. [built]** The full bond set is always
  drawn faintly (the anatomy); the bonds actually conducting at the current π are
  lit (the state). Consistent with R8 and gives the eye something stable while
  nodes flash.
- Within-level coupling constant; across-level coupling gated by (1 − precision
  index), exactly zero at π = 100. Patches are components joined by *open bonds*,
  not merely adjacent cells.
- **Opens at the transition, not below it. [built]** Default π moves off 100 to
  ~65, the stated first-breakthrough point. The figure should not open on
  `0/108 bonds open`, which is the most inert state it can produce.

**Grounding note:** Girn et al. 2026 (*Nat Med*) found increased transmodal↔unimodal
connectivity with weak-to-moderate reductions in *within*-network FC. Across-level
bonds opening while within-level holds constant is close to that; letting
within-level weaken slightly as across-level opens would be more faithful.

### Panel C — where this is in the brain

**Job:** tie the schematic to real cortex. It is the only element that does.

- **The brain currently renders at zero height.** `.brainwrap` is `flex:1 1 auto;
  min-height:0` with absolutely-positioned children, so its content height is 0
  and the `.label2` ledger below takes everything. `bBase` has `naturalWidth 1100`
  and `clientHeight 0`. The images load and draw at zero pixels.
- **The ledger moves out, the brain stays. [built]** Text in a figure panel is what
  belongs in a caption or README; the surface render is not. This also frees the
  vertical space Panel A needs.
- Hover contract: a node in A outlines its parcel here and its cell in B.

---

## 4. The three dynamical claims — one home each

This is where teratoma risk is highest, so each claim gets exactly one home (R2).

| claim | observable | home |
|---|---|---|
| **desynchronization** (Siegel 2026 *Nat Med*; data Siegel 2024 *Nature*) | relative **phase** of flashes — within-level locked at π=100, scattered at π=0 | Panel A nodes |
| **entropy increase** (REBUS) | **regularity of flash interval** — periodic at π=100, jittered at π=0 | Panel A nodes |
| **criticality** | **spatial extent of co-activation** — percolation threshold; patch span 1→4 levels, first breakthrough π≈65 | Panel B |

Criticality does **not** ride on the flashing. Flashing gives the figure a time
axis, which it needs and did not have — everything except the clicked cascade was
a static function of π. But a single instant of twinkle reads as "the brain is
on," not "this system is near a critical point." The transition is spatial and it
already lives in Panel B; it just has never been named.

**Open tension to resolve, not paper over:** Pines et al. 2026 (*PNAS*, Siegel
co-author) find psychedelics *attenuate* bottom-up signal flow magnitude and
directionality in the DMN across four datasets. The figure's most prominent
animation is an error climbing further under relaxation. These are not
necessarily contradictory — perturbation reach is not resting-state flow — but
the figure should not pretend the tension is absent.

---

## 5. Controls

- `π` slider, 100 → 0, the single independent variable. Keyboard ← → (shift =
  larger steps). Moving it re-traces a running cascade live rather than leaving a
  stale trace.
- Node-count selector, driving both A and B from one subsample.
- Channel chips: predictions, error return, level inversions.
- Theme (light/dark), Present (hides the chip row), Sweep, Freeze-frame.
- Click a node → release a perturbation. Space pauses, esc clears.

Freeze-frame compares one node at π = 85 / 55 / 15: `dies out` / `holds` /
`spreads`. That is subcritical / critical / supercritical and should be labelled
as such.

---

## 6. Non-goals

Held from v3:

- **A graph must earn its axes. [revised]** The ban on measurement axes and
  log-log panels is **lifted**. The objection was never to charts in principle —
  it was that the ones in previous versions were redundant and told a lay viewer
  nothing. The test a chart must pass before it is drawn: *does it show something
  no picture in this figure already shows, and can a non-specialist say what it
  means in one sentence?* Two noes and it does not go in. The specific failure
  mode is a chart that restates the slider; four of those have been removed
  already (disruption bars, prior halos, the generative-model cards, the ambient
  error field). The audience is lay, and an uninformative axis costs more than it
  earns.
- No new quantitative headline beyond the four-value ring row.
- No tractography, no functional connectivity. "Connection strength" in this
  figure means the scaffold's own structure plus the measured T1w/T2w level drop,
  and says so.
- No claim that any of this is a measurement of a drug effect.

**Lifted in v4:** the ban on RNG and on simulation. Replaced by R7.

---

## 7. Decisions

**Settled.**

1. **Criticality readout: σ, the branching ratio.** Critical value 1.0 on a linear
   scale. Already latent in the generation ladder — each row's width over the
   previous row's *is* σ — so it names something the figure draws rather than
   adding a new object. Per R7 it is reported as an ensemble mean over a stated
   run count and seed, never a single draw. No avalanche-size distribution: it
   needs many events not to look like noise, and it starts an argument about power
   laws that a lay audience has no stake in.
2. **Node counts.** Panel A 140/200/260/360; Panel B 8/12/16 columns, default 12,
   subset of A. See §3, Panel B.
3. **ρ border colour: `#6d1119`**, the top of the existing `rhoRamp`
   (`#d7d7d9 → #c08a83 → #a1443f → #6d1119`). It inherits the collar's identity, so
   the colourbar still means something once the collar is gone, and it sits ~40 L*
   below paralimbic `#e2761a` — separating on lightness, not hue alone, which is
   what a bright red failed to do. Dark theme steps up to `#a1443f`. If it still
   muddies at small sizes, add a 1px background-coloured gap between fill and
   border rather than changing the hue.
4. **`SQUASH` stays.** At 0.98 it is a 2% ovalization and was never the problem.
   The binding constant is `RADII`. Withdrawn as a decision.

**Settled during the build.**

5. **sigma approaches 1 from below and stops.** The model does not go
   supercritical anywhere on the slider, which is consistent with the lattice's
   existing description of bottoming out patchy rather than noise-dominated.
   Sustained sigma > 1 in cortex is a seizure, not a psychedelic. The axis
   therefore runs 0 to 1.2, not 0 to 2.
6. **One regime vocabulary.** The freeze-frame used to label its third pane
   "supercritical" off a hop count while the ensemble said sigma < 1. `regimeOf()`
   is now the only source of a regime word, and the triptych prints its pane's
   own ensemble sigma beside it. The pane's *verdict* describes that run; the
   *regime* describes the ensemble there. Two claims, no longer confusable.

**Still open.**

- Nothing blocking. Next disagreement gets recorded here rather than absorbed
  silently into the code.

---

## 8. Self-checks

The figure asserts against itself at load and fails loudly:

- `FIG.assertDirection()` — edge directions match the measured level drop.
- `FIG.assertProliferation()` — R8: target count and total drive both rise as π
  falls; mean weight per target falls.
- `FIG.censusRho()` / `FIG.censusWedge()` — the ring and sector readouts.
- `FIG.ladders(step)`, `FIG.triptych()`, `FIG.state()`.
- Every constant is in `FIG.P` and sweepable live. Tuning is done that way, not
  by eye.

**Added in v4:**
- `assertEnsemble()` — no printed number derives from a single random draw (R7):
  every reported statistic carries its run count and seed.
- `assertCols()` — `COLS` <= the smallest row count in the current subsample, so
  Panel B can never silently duplicate a parcel across columns.
- `assertSubset()` — Panel B's parcel set is a subset of Panel A's.
- Geometry moved into `P.G`, mirrored by `applyGeom()` and sweepable live from
  `FIG.setGeom({...})` — §8's claim is now true of the layout, not only the model.
