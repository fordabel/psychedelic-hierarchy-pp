# Relaxed priors

An interactive figure: how cortical 5-HT2A density sets where the hierarchical
predictive model loses its grip. A teaching illustration of the REBUS mechanism.

Open `figure.html`, or build a single self-contained file with
`python bundle_standalone.py` and open `figure_standalone.html`.

## The claim

> Cortical 5-HT2A density indexes **where** descending prediction precision
> relaxes first. Relaxing it changes **where activity can travel**, and the
> change is not uniform across the cortical hierarchy.

One slider — prior precision π — drives all three panels at once.

- **Panel A** Cortex as a directed hierarchy. Concentric rings are Mesulam
  cortical types, apex at the centre. Predictions fan outward, errors climb
  inward, nodes flash as coupled phase oscillators. Click any node to release a
  perturbation.
- **Panel B** The same parcels as a lattice network. Where activity stops being
  local: a percolation threshold you can drive through.
- **Panel C** Where this is on the cortical surface. Hover Panel A to light a
  ring or an individual parcel here.

## Reading the figure

`SPEC.md` is the governing document — the claim, the standing rules, what each
panel is for, what is measured versus schematic, and the decisions behind every
non-obvious choice. Read it before changing anything; it exists so this figure
does not become a pile of unrelated good ideas.

`SPEC-V3-NOTES.md` is a changelog for one earlier iteration and does not outrank
it.

## Inputs

Only four things are data. Everything else is scaffold, and the figure says so.

| symbol | input | source |
|---|---|---|
| ρ | cortical 5-HT2A density | Beliveau et al. 2017, [11C]Cimbi-36 PET, BP_ND parcel means |
| τ | intrinsic timescale | MEG time constants, HCP S1200 (neuromaps hcps1200/megtimescale) |
| — | edge direction | HCP S1200 group myelin map, inverted T1w/T2w |
| — | parcellation | HCP-MMP1 360 areas (Glasser 2016); Mesulam type (Paquola 2019); principal gradient (Margulies 2016) |

Nothing here is fitted, and nothing in it is a measurement of a drug effect.

## Checking it

The figure asserts against itself at load and fails loudly in the console.
Everything is re-runnable from `window.FIG`:

    FIG.assertDirection()       edges advance apex -> surface
    FIG.assertProliferation()   targets rise and per-target weight falls
    FIG.assertCols()            no parcel is repeated across Panel B columns
    FIG.assertSubset()          Panel B's parcels are a subset of Panel A's
    FIG.assertEnsemble()        sigma is an ensemble, reproducible from its seed
    FIG.censusRho()             5-HT2A percentile by cortical type
    FIG.state() / FIG.P         every constant, sweepable live
    FIG.setGeom({CX: 400})      geometry too

## Regenerating assets

`assets/` is committed because rebuilding it needs network access and the
neuroimaging stack. `build_assets.py` is what built it; `rerender_surfaces.py`
redraws the cortical surface renders alone.
