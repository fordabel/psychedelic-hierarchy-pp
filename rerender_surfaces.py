#!/usr/bin/env python3
"""Re-render Panel B only, from data already on disk.

Group 2 / FIX 7 needs two things the baked PNGs cannot provide:

  1. A CATEGORICAL Mesulam palette. The shipped `palette.json` ring ramp was
     built as mix_hex(anchor, TRANSMODAL, CONVERGENCE[r]) -- a two-endpoint
     blue->orange interpolation sampled at four points. Measured in OKLab the
     four colours are collinear to within 0.001, and the two middle classes sit
     in the low-chroma centre of that line, which is exactly why the surface
     reads as "blue at one end, orange at the other, mush in between".

  2. A parcel ID map, so hovering one node in Panel A can outline that one
     parcel on the surface. There is no per-parcel asset today and 360 PNGs is
     not an option, so this writes a single flat, unshaded, un-antialiased
     render with the parcel index encoded in RGB.

NOTHING IS RE-FETCHED. This reads cache/*.annot and the nilearn fsaverage
cache, plus assets/parcels.json for the per-parcel class assignments that
build_assets.py already computed. No neuromaps call, no network.
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import build_assets as B  # noqa: E402

ASSETS = Path(__file__).parent / "assets"

# --- the new canonical Mesulam hues -------------------------------------
# Chosen for categorical separation, not for a ramp: min pairwise OKLab
# distance 0.132 (was 0.075), min hue gap 63 deg (was 13), and lightness still
# increases monotonically inward so the ordinal reading survives. Every one
# clears 3.0:1 against the dark panel and 3.0:1 against white.
RING_CAT = ["#3a78c0", "#17958c", "#9b76d8", "#e2761a"]


def render_flat(meshes, ids, vert, colour_of_parcel, out_path, dpi):
    """render_views() with lighting and antialiasing switched off.

    The ID map has to survive a pixel lookup, so a face must land on screen as
    exactly the RGB it was assigned -- no lambert term, no edge blending.
    """
    import matplotlib
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    wall = B.hex_to_rgb(B.MEDIAL_WALL)
    panels = [("L", 180, 0), ("R", 0, 1), ("L", 0, 2), ("R", 180, 3)]
    fig = plt.figure(figsize=(9.2, 6.6))
    fig.patch.set_alpha(0.0)
    for hemi, azim, slot in panels:
        coords, faces = meshes[hemi]
        codes = vert[hemi]
        lut = np.zeros((len(ids) + 1, 3))
        lut[len(ids)] = wall
        for p, k in enumerate(ids):
            lut[p] = B.hex_to_rgb(colour_of_parcel(k))
        vcode = np.where(codes < 0, len(ids), codes)
        fcode = B.face_labels(faces, vcode)
        fcol = lut[fcode]
        tri = coords[faces]
        ax = fig.add_subplot(2, 2, slot + 1, projection="3d")
        ax.set_proj_type("ortho")
        pc = Poly3DCollection(
            tri, facecolors=fcol, edgecolors=fcol, linewidths=0.0,
            shade=False, antialiased=False,
        )
        pc.set_zsort("average")
        ax.add_collection3d(pc)
        lo, hi = coords.min(axis=0), coords.max(axis=0)
        pad = 0.02 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        try:
            ax.set_box_aspect(tuple(hi - lo), zoom=1.12)
        except TypeError:
            ax.set_box_aspect(tuple(hi - lo))
        ax.view_init(elev=0, azim=azim)
        ax.set_axis_off()
        ax.patch.set_alpha(0.0)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=-0.04, hspace=-0.10)
    fig.savefig(out_path, dpi=dpi, transparent=True)
    plt.close(fig)
    print(f"  wrote {out_path.name}")


def id_hex(i):
    """Parcel index -> an exact RGB triple that survives a pixel lookup.

    Spread across the cube (index * a large odd stride) rather than packed into
    the low byte, so that if any pixel does get blended between two parcels the
    result is very unlikely to decode as a third valid parcel.
    """
    v = ((i + 1) * 2654435761) & 0xFFFFFF
    return f"#{v:06x}"


def main():
    dpi = int(sys.argv[1]) if len(sys.argv) > 1 else 190
    pal = json.loads((ASSETS / "palette.json").read_text())
    recs = json.loads((ASSETS / "parcels.json").read_text())
    by_id = {d["id"]: d for d in recs}

    print("[1/4] loading meshes + parcellation (cache only, no network)")
    meshes = B.load_fsaverage_meshes()
    ids, _index, vert = B.parcellate_fsaverage()
    print(f"  {len(ids)} parcels on the surface, {len(recs)} in parcels.json")

    pal["ring"] = list(RING_CAT)
    pal["ringCategorical"] = True

    print("[2/4] rendering Mesulam-type surfaces with the categorical palette")

    def ring_colour(k):
        d = by_id.get(k)
        return RING_CAT[d["ring"]] if d else B.NEUTRAL_PARCEL

    B.render_views(meshes, ids, vert, ring_colour, ASSETS / "brain_rings.png", dpi)

    for r in range(4):
        def one(k, r=r):
            d = by_id.get(k)
            return RING_CAT[r] if (d and d["ring"] == r) else B.NEUTRAL_PARCEL
        B.render_views(meshes, ids, vert, one, ASSETS / f"brain_ring_{r}.png", dpi)

    print("[3/4] rendering the sensory-stream surface (modality, demoted)")

    def stream_colour(k):
        d = by_id.get(k)
        if not d:
            return B.NEUTRAL_PARCEL
        return B.MODALITY_BASE.get(d.get("stream")) or B.NEUTRAL_PARCEL

    B.render_views(meshes, ids, vert, stream_colour, ASSETS / "brain_stream.png", dpi)

    def rho_colour(k):
        d = by_id.get(k)
        return B.ramp_hex(B.RHO_RAMP, d["rhoRank"]) if d else B.NEUTRAL_PARCEL

    B.render_views(meshes, ids, vert, rho_colour, ASSETS / "brain_rho.png", dpi)

    print("[4/4] rendering the parcel ID map (flat, unshaded, no antialiasing)")
    idx_of = {k: i for i, k in enumerate(ids)}
    render_flat(meshes, ids, vert,
                lambda k: id_hex(idx_of[k]), ASSETS / "brain_ids.png", dpi)

    B.crop_common(
        [ASSETS / n for n in (
            "brain_rings.png", "brain_stream.png", "brain_rho.png",
            "brain_ids.png",
        )] + [ASSETS / f"brain_ring_{r}.png" for r in range(4)]
    )

    # the id -> parcel mapping the page needs to decode brain_ids.png
    pal["parcelIds"] = ids
    pal["idKey"] = [id_hex(i) for i in range(len(ids))]
    (ASSETS / "palette.json").write_text(json.dumps(pal, indent=1))
    print(f"  palette.json updated ({len(ids)} id keys)")

    # mirror into data.js so file:// still works
    js = (ASSETS / "data.js").read_text()
    head = js[: js.index("window.FIGURE_DATA = ")]
    body = js[js.index("window.FIGURE_DATA = ") + len("window.FIGURE_DATA = "):].rstrip().rstrip(";")
    D = json.loads(body)
    D["palette"] = pal
    (ASSETS / "data.js").write_text(head + "window.FIGURE_DATA = " + json.dumps(D, indent=1) + ";\n")
    print("  data.js palette mirrored")
    print("done.")


if __name__ == "__main__":
    main()
