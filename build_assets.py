#!/usr/bin/env python3
"""
build_assets.py -- Stage 1 data layer for the cortical-hierarchy figure.

Produces assets/parcels.json (one record per HCP-MMP cortical parcel) and a set
of transparent-background surface renders that Panel B uses as a lookup table.

Every quantity written out is measured from a published dataset. Nothing here is
synthetic. Provenance for each field is written to assets/sources.json and shown
in the figure itself.

Spaces
------
  ring, modality, rho   fsaverage 164k   (HCP-MMP annot, Mesulam annot, Beliveau PET)
  gradient              fsLR 32k         (HCP-MMP dlabel, Margulies gradient)

The two spaces are never resampled into each other. Each map is averaged inside
its own native-space version of the *same* parcellation and the results are
joined on parcel name, so no surface-to-surface transform (and no Connectome
Workbench) is required.

Usage:  python build_assets.py [--skip-render] [--dpi 200]
"""

import argparse
import json
import os
import shutil
import sys
import urllib.request
from collections import Counter, OrderedDict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
ASSETS = HERE / "assets"

# --------------------------------------------------------------------------
# Palette. Defined once, here, and exported to the HTML so Panel A and Panel B
# cannot drift apart.
# --------------------------------------------------------------------------
MODALITY_BASE = OrderedDict(
    [("visual", "#2a78d6"), ("auditory", "#6250d6"), ("somatomotor", "#1baf7a")]
)
TRANSMODAL = "#eb6834"
CONVERGENCE = [0.0, 0.26, 0.66, 1.0]  # per ring, outward -> inward
NEUTRAL_PARCEL = "#b9bcc0"  # un-highlighted parcels in brain_ring_N.png
MEDIAL_WALL = "#7d8288"
RHO_RAMP = ["#d7d7d9", "#c08a83", "#a1443f", "#6d1119"]  # grey -> dark red

# Parcels whose surface-projected PET value is essentially zero are allocortical
# (hippocampus proper) where a volumetric PET map has no valid cortical-ribbon
# signal. They are kept in the data but excluded from the normalisation range so
# two artefactual zeros do not compress the whole scale.
RHO_VALID_FLOOR = 1.0

RING_NAMES = ["idiotypic", "unimodal", "heteromodal", "paralimbic"]
RING_LONG = [
    "idiotypic (primary sensory / motor)",
    "unimodal association",
    "heteromodal association",
    "paralimbic",
]

# Mesulam annot label index -> ring index (outward 0 .. inward 3).
# The annot's own colour-table names are read at runtime and checked against this.
MESULAM_NAME_TO_RING = {
    "idiotypic": 0,
    "unimodal": 1,
    "heteromodal": 2,
    "paralimbic": 3,
}

# Glasser's 22 cortical divisions -> sensory stream. Only divisions that are
# unambiguously one modality are mapped; everything else stays None.
DIVISION_TO_MODALITY = {
    "Primary Visual Cortex (V1)": "visual",
    "Early Visual Cortex": "visual",
    "Dorsal Stream Visual Cortex": "visual",
    "Ventral Stream Visual Cortex": "visual",
    "MT+ Complex and Neighboring Visual Areas": "visual",
    "Somatosensory and Motor Cortex": "somatomotor",
    "Paracentral Lobular and Mid Cingulate Cortex": "somatomotor",
    "Premotor Cortex": "somatomotor",
    "Posterior Opercular Cortex": "somatomotor",
    "Early Auditory Cortex": "auditory",
    "Auditory Association Cortex": "auditory",
}

REMOTE = {
    "lh.HCPMMP1.annot": "https://ndownloader.figshare.com/files/5528816",
    "rh.HCPMMP1.annot": "https://ndownloader.figshare.com/files/5528819",
    "lh.mesulam.annot": "https://raw.githubusercontent.com/MICA-MNI/micaopen/master/MPC/maps/lh.mesulam.annot",
    "rh.mesulam.annot": "https://raw.githubusercontent.com/MICA-MNI/micaopen/master/MPC/maps/rh.mesulam.annot",
    "glasser_fsLR32k.dlabel.nii": "https://raw.githubusercontent.com/PennLINC/S-A_ArchetypalAxis/main/FSLRVertex/SensorimotorAssociation_Axis_parcellated/atlas_dlabel_files/glasser_space-fsLR_den-32k_desc-atlas.dlabel.nii",
    "mne_utils.py": "https://raw.githubusercontent.com/mne-tools/mne-python/main/mne/datasets/utils.py",
}


def die(dataset, err):
    """Stop loudly. We never substitute a synthetic value for a failed fetch."""
    print("\n" + "=" * 72, file=sys.stderr)
    print(f"STOPPING -- could not obtain: {dataset}", file=sys.stderr)
    print(f"  {type(err).__name__}: {err}", file=sys.stderr)
    print("No synthetic values were written. Fix the fetch and re-run.", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    sys.exit(2)


def cached(name):
    CACHE.mkdir(exist_ok=True)
    dest = CACHE / name
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = REMOTE[name]
    print(f"  fetching {name} ...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "build_assets/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:  # noqa: BLE001
        if dest.exists():
            dest.unlink()
        die(name, e)
    return dest


# --------------------------------------------------------------------------
# Colour maths. Mixing happens in OKLab so the modality -> transmodal ramp keeps
# its chroma instead of collapsing through grey at the midpoint.
# --------------------------------------------------------------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])


def rgb_to_hex(c):
    c = np.clip(c, 0, 1)
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c)


def _srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def rgb_to_oklab(c):
    r, g, b = _srgb_to_lin(np.asarray(c, float))
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.array(
        [
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ]
    )


def oklab_to_rgb(lab):
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    lin = np.array(
        [
            4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
        ]
    )
    return _lin_to_srgb(lin)


def mix_hex(a, b, t):
    return rgb_to_hex(
        oklab_to_rgb(rgb_to_oklab(hex_to_rgb(a)) * (1 - t) + rgb_to_oklab(hex_to_rgb(b)) * t)
    )


def ramp_hex(stops, t):
    t = float(np.clip(t, 0, 1)) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    return mix_hex(stops[i], stops[i + 1], t - i)


def build_palette():
    """Modality colour at each ring depth, plus the ring ramp Panel B paints."""
    modality_by_ring = {
        m: [mix_hex(base, TRANSMODAL, c) for c in CONVERGENCE]
        for m, base in MODALITY_BASE.items()
    }
    # The ring ramp anchors on the mean of the three modality colours in OKLab,
    # then follows exactly the same convergence schedule the nodes follow.
    anchor_lab = np.mean([rgb_to_oklab(hex_to_rgb(h)) for h in MODALITY_BASE.values()], axis=0)
    anchor = rgb_to_hex(oklab_to_rgb(anchor_lab))
    ring = [mix_hex(anchor, TRANSMODAL, c) for c in CONVERGENCE]
    return {
        "modalityBase": dict(MODALITY_BASE),
        "modalityByRing": modality_by_ring,
        "transmodal": TRANSMODAL,
        "convergence": CONVERGENCE,
        "ring": ring,
        "ringAnchor": anchor,
        "neutralParcel": NEUTRAL_PARCEL,
        "medialWall": MEDIAL_WALL,
        "rhoRamp": RHO_RAMP,
        "ringNames": RING_NAMES,
        "ringLong": RING_LONG,
    }


def node_colour(pal, ring, stream):
    """The colour of one parcel, everywhere it appears.

    A parcel property only -- its sensory stream and its Mesulam type. Panel A
    and Panel B therefore paint the same parcel the same colour, which is the
    only way a viewer can find a node from the ring diagram on the surface.
    """
    base = MODALITY_BASE.get(stream) or pal["ringAnchor"]
    return mix_hex(base, TRANSMODAL, CONVERGENCE[ring])


# --------------------------------------------------------------------------
# Parcellation + maps
# --------------------------------------------------------------------------
def norm_area(name):
    """'L_V1_ROI' / b'R_V1_ROI' -> ('L', 'V1')."""
    if isinstance(name, bytes):
        name = name.decode()
    hemi = None
    if name[:2] in ("L_", "R_"):
        hemi, name = name[0], name[2:]
    if name.endswith("_ROI"):
        name = name[:-4]
    return hemi, name


def _groups(codes, n):
    """Vertex indices grouped by parcel code, without a per-parcel full scan."""
    order = np.argsort(codes, kind="stable")
    sc = codes[order]
    lo = np.searchsorted(sc, np.arange(n), side="left")
    hi = np.searchsorted(sc, np.arange(n), side="right")
    return order, lo, hi


def load_glasser_divisions():
    """The published 22 cortical divisions, read out of mne-python's source."""
    src = cached("mne_utils.py").read_text()
    try:
        i = src.index("groups = OrderedDict(")
        j = src.index("(", i + len("groups = OrderedDict") - 1)
        depth, k = 0, j
        while True:
            if src[k] == "(":
                depth += 1
            elif src[k] == ")":
                depth -= 1
            if depth == 0:
                break
            k += 1
        ns = {"OrderedDict": OrderedDict}
        exec(src[i : k + 1], ns)  # noqa: S102
        groups = ns["groups"]
    except Exception as e:  # noqa: BLE001
        die("Glasser cortical divisions (mne-python HCPMMP1_combined grouping)", e)
    area_to_div = {}
    for div, areas in groups.items():
        if div.strip("?") == "":
            continue
        for a in areas:
            area_to_div[a] = div
    return area_to_div


def parcellate_fsaverage():
    """-> ids (list of 'L_V1'...), index, vert[hemi] = int code per vertex (-1 = none)."""
    import nibabel as nib

    ids, index, vert = [], {}, {}
    for hemi, tag in (("L", "lh"), ("R", "rh")):
        lab, _, names = nib.freesurfer.read_annot(str(cached(f"{tag}.HCPMMP1.annot")))
        names = [n.decode() if isinstance(n, bytes) else n for n in names]
        codes = np.full(len(names), -1, dtype=np.int32)
        for i, n in enumerate(names):
            _, a = norm_area(n)
            if a in ("???", ""):
                continue
            key = f"{hemi}_{a}"
            if key not in index:
                index[key] = len(ids)
                ids.append(key)
            codes[i] = index[key]
        lab = np.asarray(lab)
        lab[lab < 0] = 0
        vert[hemi] = codes[lab]
    return ids, index, vert


def parcellate_mesulam(ids, vert):
    import nibabel as nib

    out, purity, seen_names = {}, {}, None
    for hemi, tag in (("L", "lh"), ("R", "rh")):
        lab, _, names = nib.freesurfer.read_annot(str(cached(f"{tag}.mesulam.annot")))
        names = [n.decode() if isinstance(n, bytes) else n for n in names]
        seen_names = names
        ring_of_idx = np.array([MESULAM_NAME_TO_RING.get(n, -1) for n in names], dtype=np.int32)
        lab = np.asarray(lab)
        lab[lab < 0] = 0
        rings = ring_of_idx[lab]
        codes = vert[hemi]
        order, lo, hi = _groups(codes, len(ids))
        for p in range(len(ids)):
            if hi[p] <= lo[p]:
                continue
            r = rings[order[lo[p] : hi[p]]]
            r = r[r >= 0]
            if r.size == 0:
                continue
            cnt = np.bincount(r, minlength=4)
            out[ids[p]] = int(cnt.argmax())
            purity[ids[p]] = float(cnt.max() / r.size)
    if not set(MESULAM_NAME_TO_RING).issubset(set(seen_names or [])):
        die("Mesulam annot colour table", ValueError(f"unexpected class names: {seen_names}"))
    return out, purity


def parcellate_surface_map(ids, vert, lh_path, rh_path):
    import nibabel as nib

    out = {}
    for hemi, path in (("L", lh_path), ("R", rh_path)):
        data = np.asarray(nib.load(str(path)).agg_data(), dtype=float).ravel()
        codes = vert[hemi]
        if data.size != codes.size:
            die(
                f"surface map {Path(path).name}",
                ValueError(f"{data.size} vertices vs {codes.size} in parcellation"),
            )
        order, lo, hi = _groups(codes, len(ids))
        for p in range(len(ids)):
            if hi[p] <= lo[p]:
                continue
            v = data[order[lo[p] : hi[p]]]
            v = v[np.isfinite(v)]
            if v.size:
                out[ids[p]] = float(v.mean())
    return out


_FSLR_CODES = {}


def fslr32k_codes(ids, index):
    """Glasser dlabel in fsLR 32k -> per-vertex parcel code. Built once."""
    import nibabel as nib

    if _FSLR_CODES:
        return _FSLR_CODES
    img = nib.load(str(cached("glasser_fsLR32k.dlabel.nii")))
    label_tab = img.header.get_axis(0).label[0]
    bm = img.header.get_axis(1)
    data = np.asarray(img.get_fdata()).ravel()

    for struct, sl, model in bm.iter_structures():
        up = struct.upper()
        hemi = "L" if "LEFT" in up else "R" if "RIGHT" in up else None
        if hemi is None:
            continue
        codes = np.full(model.nvertices[struct], -1, dtype=np.int32)
        vals = data[sl].astype(int)
        for v_idx, code in zip(model.vertex, vals):
            nm = label_tab.get(int(code), ("???",))[0]
            _, a = norm_area(nm)
            if a not in ("???", ""):
                codes[v_idx] = index.get(f"{hemi}_{a}", -1)
        _FSLR_CODES[hemi] = codes
    return _FSLR_CODES


def parcellate_fslr32k(ids, codes_by_hemi, lh, rh, label="fsLR 32k map"):
    """Average an fsLR 32k surface map inside each parcel, in its own space."""
    import nibabel as nib

    out = {}
    for hemi, path in (("L", lh), ("R", rh)):
        vals = np.asarray(nib.load(str(path)).agg_data(), dtype=float).ravel()
        codes = codes_by_hemi[hemi]
        if vals.size != codes.size:
            die(label, ValueError(f"{vals.size} vertices vs {codes.size} in the dlabel"))
        order, lo, hi = _groups(codes, len(ids))
        for p in range(len(ids)):
            if hi[p] <= lo[p]:
                continue
            v = vals[order[lo[p] : hi[p]]]
            v = v[np.isfinite(v) & (v != 0)]
            if v.size:
                out[ids[p]] = float(v.mean())
    return out


def fetch_fslr(source, desc, den):
    from neuromaps.datasets import fetch_annotation

    try:
        ann = fetch_annotation(source=source, desc=desc, space="fsLR", den=den)
    except Exception as e:  # noqa: BLE001
        die(f"neuromaps {source}/{desc}/fsLR/{den}", e)
    return (ann[0], ann[1]) if isinstance(ann, (list, tuple)) else (ann["L"], ann["R"])


def fslr_spheres(den):
    from neuromaps.datasets import fetch_atlas

    try:
        atl = fetch_atlas("fsLR", den)
    except Exception as e:  # noqa: BLE001
        die(f"fsLR {den} sphere surfaces (neuromaps fetch_atlas)", e)
    sph = atl["sphere"]
    return str(sph[0]), str(sph[1])


def upsample_4k_to_32k(lh4, rh4):
    """fsLR 4k -> fsLR 32k by nearest neighbour on the sphere.

    neuromaps' own 4k->32k transform shells out to Connectome Workbench, which
    this pipeline deliberately does not depend on. Instead each fsLR 32k vertex
    takes the value of the angularly nearest fsLR 4k vertex. That is a
    nearest-neighbour resample, not an areal one, and it is disclosed as such
    in sources.json.
    """
    import nibabel as nib

    l4, r4 = fslr_spheres("4k")
    l32, r32 = fslr_spheres("32k")
    out = {}
    for hemi, vpath, s4, s32 in (("L", lh4, l4, l32), ("R", rh4, r4, r32)):
        vals = np.asarray(nib.load(str(vpath)).agg_data(), dtype=float).ravel()
        c4 = np.asarray(nib.load(s4).agg_data()[0], dtype=np.float64)
        c32 = np.asarray(nib.load(s32).agg_data()[0], dtype=np.float64)
        if vals.size != c4.shape[0]:
            die("fsLR 4k map", ValueError(f"{vals.size} values vs {c4.shape[0]} vertices"))
        c4 /= np.linalg.norm(c4, axis=1, keepdims=True)
        c32 /= np.linalg.norm(c32, axis=1, keepdims=True)
        nn = np.empty(c32.shape[0], dtype=np.int64)
        for i in range(0, c32.shape[0], 4096):
            nn[i : i + 4096] = (c32[i : i + 4096] @ c4.T).argmax(axis=1)
        out[hemi] = vals[nn]
    return out


def parcellate_gradient(ids, index):
    """Margulies gradient stays in fsLR 32k and is averaged inside the fsLR dlabel."""
    lh, rh = fetch_fslr("margulies2016", "fcgradient01", "32k")
    return parcellate_fslr32k(ids, fslr32k_codes(ids, index), lh, rh,
                              "Margulies gradient / fsLR dlabel")


def fetch_beliveau():
    from neuromaps.datasets import fetch_annotation

    try:
        ann = fetch_annotation(
            source="beliveau2017", desc="cimbi36", space="fsaverage", den="164k"
        )
    except Exception as e:  # noqa: BLE001
        die("Beliveau 2017 5-HT2A Cimbi-36 (neuromaps beliveau2017/cimbi36/fsaverage/164k)", e)
    return (ann[0], ann[1]) if isinstance(ann, (list, tuple)) else (ann["L"], ann["R"])


# --------------------------------------------------------------------------
# Rendering. Explicit per-face colours + a simple Lambert term, so the surface
# reads as a brain while every colour is exactly the hex Panel A uses.
# --------------------------------------------------------------------------
def load_fsaverage_meshes():
    from nilearn import datasets as nds
    from nilearn import surface

    try:
        fs = nds.load_fsaverage("fsaverage")
        infl = fs["inflated"]
        return {
            "L": (np.asarray(infl.parts["left"].coordinates), np.asarray(infl.parts["left"].faces)),
            "R": (np.asarray(infl.parts["right"].coordinates), np.asarray(infl.parts["right"].faces)),
        }
    except Exception:  # noqa: BLE001
        fs = nds.fetch_surf_fsaverage("fsaverage")
        out = {}
        for hemi, key in (("L", "infl_left"), ("R", "infl_right")):
            c, f = surface.load_surf_mesh(fs[key])
            out[hemi] = (np.asarray(c), np.asarray(f))
        return out


def face_labels(faces, vlab):
    """Categorical downsample: the label holding a majority of the triangle."""
    a, b, c = vlab[faces[:, 0]], vlab[faces[:, 1]], vlab[faces[:, 2]]
    out = a.copy()
    out = np.where(b == c, b, out)
    out = np.where(a == b, a, out)
    out = np.where(a == c, a, out)
    return out


def render_views(meshes, ids, vert, colour_of_parcel, out_path, dpi):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    wall = hex_to_rgb(MEDIAL_WALL)
    light = np.array([0.35, 0.25, 0.90])
    light = light / np.linalg.norm(light)

    panels = [("L", 180, 0), ("R", 0, 1), ("L", 0, 2), ("R", 180, 3)]  # lat L, lat R, med L, med R
    fig = plt.figure(figsize=(9.2, 6.6))
    fig.patch.set_alpha(0.0)

    for hemi, azim, slot in panels:
        coords, faces = meshes[hemi]
        codes = vert[hemi]
        lut = np.zeros((len(ids) + 1, 3))
        lut[len(ids)] = wall
        for p, k in enumerate(ids):
            lut[p] = hex_to_rgb(colour_of_parcel(k))
        vcode = np.where(codes < 0, len(ids), codes)
        fcode = face_labels(faces, vcode)
        fcol = lut[fcode]

        tri = coords[faces]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        nn = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.where(nn == 0, 1, nn)
        if hemi == "R":
            pass
        lam = np.abs(n @ light)
        shade = (0.62 + 0.38 * lam)[:, None]
        fcol = np.clip(fcol * shade, 0, 1)

        ax = fig.add_subplot(2, 2, slot + 1, projection="3d")
        ax.set_proj_type("ortho")
        pc = Poly3DCollection(tri, facecolors=fcol, linewidths=0, shade=False)
        pc.set_zsort("average")
        ax.add_collection3d(pc)

        lo, hi = coords.min(axis=0), coords.max(axis=0)
        pad = 0.02 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        ax.set_xlim(lo[0], hi[0])
        ax.set_ylim(lo[1], hi[1])
        ax.set_zlim(lo[2], hi[2])
        try:
            ax.set_box_aspect(tuple(hi - lo), zoom=1.12)
        except TypeError:  # matplotlib < 3.6
            ax.set_box_aspect(tuple(hi - lo))
        ax.view_init(elev=0, azim=azim)
        ax.set_axis_off()
        ax.patch.set_alpha(0.0)

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=-0.04, hspace=-0.10)
    fig.savefig(out_path, dpi=dpi, transparent=True)
    plt.close(fig)
    print(f"  wrote {out_path.name}")



def crop_common(paths):
    """Trim all renders to one shared alpha bounding box so the Panel B overlays
    stay pixel-aligned when they cross-fade."""
    from PIL import Image

    imgs = [(q, Image.open(q).convert("RGBA")) for q in paths if q.exists()]
    if not imgs:
        return
    box = None
    for _, im in imgs:
        bb = im.getchannel("A").getbbox()
        if bb is None:
            continue
        box = bb if box is None else (
            min(box[0], bb[0]), min(box[1], bb[1]),
            max(box[2], bb[2]), max(box[3], bb[3]),
        )
    if box is None:
        return
    pad = 6
    w, h = imgs[0][1].size
    box = (max(0, box[0] - pad), max(0, box[1] - pad),
           min(w, box[2] + pad), min(h, box[3] + pad))
    for q, im in imgs:
        im.crop(box).save(q)
    print(f"  cropped {len(imgs)} renders to {box[2]-box[0]}x{box[3]-box[1]}")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--dpi", type=int, default=190)
    args = ap.parse_args()

    ASSETS.mkdir(exist_ok=True)
    pal = build_palette()

    print("[1/8] parcellation (HCP-MMP 360, fsaverage 164k)")
    ids, index, vert = parcellate_fsaverage()
    parcels = OrderedDict(
        (k, {"id": k, "name": k.split("_", 1)[1], "hemi": k[0]}) for k in ids
    )
    print(f"      {len(parcels)} parcels")

    print("[2/8] Mesulam cortical type -> ring")
    ring, purity = parcellate_mesulam(ids, vert)

    print("[3/8] Beliveau 5-HT2A Cimbi-36 -> rho")
    lh_b, rh_b = fetch_beliveau()
    rho_raw = parcellate_surface_map(ids, vert, lh_b, rh_b)

    print("[4/8] Margulies principal gradient (fsLR 32k)")
    grad = parcellate_gradient(ids, index)

    print("[5/8] T1w/T2w myelin -> hierarchical level (fsLR 32k)")
    codes = fslr32k_codes(ids, index)
    lh_m, rh_m = fetch_fslr("hcps1200", "myelinmap", "32k")
    myelin = parcellate_fslr32k(ids, codes, lh_m, rh_m, "HCP S1200 myelin map")

    print("[6/8] MEG intrinsic timescale -> tau (fsLR 4k -> 32k, nearest neighbour)")
    lh_t, rh_t = fetch_fslr("hcps1200", "megtimescale", "4k")
    up = upsample_4k_to_32k(lh_t, rh_t)
    tau_raw = {}
    for hemi in ("L", "R"):
        vals, cds = up[hemi], codes[hemi]
        order, lo, hi = _groups(cds, len(ids))
        for pi in range(len(ids)):
            if hi[pi] <= lo[pi]:
                continue
            v = vals[order[lo[pi] : hi[pi]]]
            v = v[np.isfinite(v) & (v != 0)]
            if v.size:
                tau_raw[ids[pi]] = float(v.mean())

    print("[7/8] modality from Glasser cortical divisions")
    area_to_div = load_glasser_divisions()

    # assemble
    # level: high = deep in the hierarchy = INNER ring. T1w/T2w myelin runs the
    # other way (high in primary sensory cortex), so it is inverted here. This is
    # what gives every edge its direction, so its sign matters more than anything
    # else in this file.
    mye_vals = np.array([myelin[k] for k in parcels if k in myelin], dtype=float)
    mlo, mhi = float(mye_vals.min()), float(mye_vals.max())
    level = {k: (mhi - v) / (mhi - mlo) for k, v in myelin.items()}

    all_rho = np.array([rho_raw[k] for k in parcels if k in rho_raw], dtype=float)
    ok = all_rho[all_rho > RHO_VALID_FLOOR]
    rmin, rmax = float(ok.min()), float(ok.max())
    n_invalid = int((all_rho <= RHO_VALID_FLOOR).sum())
    recs, dropped = [], []
    for k, p in parcels.items():
        missing = next((f for f, d in (("ring", ring), ("rho", rho_raw), ("grad", grad),
                                       ("level", level), ("tau", tau_raw)) if k not in d), None)
        if missing:
            dropped.append((k, missing))
            continue
        r = ring[k]
        div = area_to_div.get(p["name"])
        # `stream` is the parcel's own sensory stream wherever Glasser's division
        # names one, at every ring -- it is what colour encodes. `modality` is
        # the same thing restricted to rings 0-1, and only drives the angular
        # sectors, where a stream is a radial slice of the diagram.
        stream = DIVISION_TO_MODALITY.get(div)
        mod = stream if r <= 1 else None
        recs.append(
            {
                "id": k,
                "name": p["name"],
                "hemi": p["hemi"],
                "ring": int(r),
                "modality": mod,
                "stream": stream,
                "gradient": round(grad[k], 6),
                "rho": round(float(np.clip((rho_raw[k] - rmin) / (rmax - rmin), 0, 1)), 6),
                "rhoValid": bool(rho_raw[k] > RHO_VALID_FLOOR),
                "division": div,
                "ringPurity": round(purity.get(k, float("nan")), 3),
                "rhoRaw": round(rho_raw[k], 6),
                "level": round(level[k], 6),
                "myelin": round(myelin[k], 6),
                "tau": round(tau_raw[k], 6),
            }
        )
    # Percentile rank of the measured density. Same ordering as rho, even spacing;
    # this is what the figure encodes visually (disclosed in the sources block).
    order = sorted(range(len(recs)), key=lambda i: recs[i]["rhoRaw"])
    for rank, i in enumerate(order):
        recs[i]["rhoRank"] = round((rank + 0.5) / len(recs), 6)
    # Same trick for tau. The MEG timescale distribution is right-skewed (a
    # handful of parcels sit 2.5x the median), so a linear encoding puts almost
    # every node at the small end of the radius scale.
    order = sorted(range(len(recs)), key=lambda i: recs[i]["tau"])
    for rank, i in enumerate(order):
        recs[i]["tauRank"] = round((rank + 0.5) / len(recs), 6)

    recs.sort(key=lambda d: (d["ring"], d["modality"] or "~", d["gradient"]))

    # ---- summary table -----------------------------------------------------
    mods = ["visual", "auditory", "somatomotor", None]
    print("\n" + "=" * 68)
    print("PARCEL COUNTS PER (ring, modality)   -- sanity check before rendering")
    print("=" * 68)
    hdr = f"{'ring':<28}" + "".join(f"{(m or 'none'):>12}" for m in mods) + f"{'total':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in range(4):
        row = [sum(1 for d in recs if d["ring"] == r and d["modality"] == m) for m in mods]
        print(f"{r} {RING_LONG[r]:<26}" + "".join(f"{v:>12}" for v in row) + f"{sum(row):>8}")
    print("-" * len(hdr))
    tot = [sum(1 for d in recs if d["modality"] == m) for m in mods]
    print(f"{'total':<28}" + "".join(f"{v:>12}" for v in tot) + f"{sum(tot):>8}")
    print("=" * len(hdr))

    # ---- level / tau by ring: the check that has to pass before rendering ---
    print("\n" + "=" * 78)
    print("LEVEL AND TAU BY RING   -- level MUST increase inward (ring 0 -> ring 3)")
    print("=" * 78)
    hdr2 = (f"{'ring':<28}{'n':>4}{'level':>18}{'T1w/T2w':>11}{'tau (MEG)':>18}")
    print(hdr2)
    print("-" * len(hdr2))
    lev_by_ring, tau_by_ring = [], []
    for r in range(4):
        sub_ = [d for d in recs if d["ring"] == r]
        lv = np.array([d["level"] for d in sub_])
        my = np.array([d["myelin"] for d in sub_])
        tv = np.array([d["tau"] for d in sub_])
        lev_by_ring.append(lv.mean())
        tau_by_ring.append(tv.mean())
        print(f"{r} {RING_LONG[r]:<26}{len(sub_):>4}"
              f"{lv.mean():>11.3f} ±{lv.std():<5.3f}"
              f"{my.mean():>11.3f}"
              f"{tv.mean():>11.4f} ±{tv.std():<6.4f}")
    print("-" * len(hdr2))
    mono = all(lev_by_ring[i] < lev_by_ring[i + 1] for i in range(3))
    print(f"level increases inward, ring by ring: {'YES' if mono else 'NO'}"
          f"   ({' < '.join(f'{v:.3f}' for v in lev_by_ring)})")
    tmono = all(tau_by_ring[i] < tau_by_ring[i + 1] for i in range(3))
    print(f"tau   increases inward, ring by ring: {'YES' if tmono else 'NO'}"
          f"   ({' < '.join(f'{v:.4f}' for v in tau_by_ring)})")
    lv_all = np.array([d["level"] for d in recs])
    rg_all = np.array([d["ring"] for d in recs], dtype=float)
    tv_all = np.array([d["tau"] for d in recs])
    gd_all = np.array([d["gradient"] for d in recs])

    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        return float(np.corrcoef(ra, rb)[0, 1])

    print(f"level x ring      Spearman rho = {spearman(lv_all, rg_all):+.3f}   "
          f"(independent check: level was never told about the ring)")
    print(f"level x gradient  Spearman rho = {spearman(lv_all, gd_all):+.3f}")
    print(f"tau   x level     Spearman rho = {spearman(tv_all, lv_all):+.3f}")
    print(f"tau   x ring      Spearman rho = {spearman(tv_all, rg_all):+.3f}")
    print("=" * len(hdr2))
    if not mono:
        print("\nWARNING: level does not increase monotonically across the four Mesulam")
        print("classes. Every prediction/error arrow in the figure is drawn from this")
        print("field, so read the table above before trusting the picture.")

    odd = [d for d in recs if d["ring"] == 0 and d["stream"] is None]
    if odd:
        print("\nIDIOTYPIC parcels with no sensory stream label "
              "(Mesulam calls them idiotypic; Glasser's division names no stream):")
        for d in odd:
            print(f"  {d['id']:12s} {d['division']:32s} ring purity {d['ringPurity']:.2f}")
        print("  Low ring purity means the Mesulam class was close to a tie for that parcel.")

    pur = np.array([d["ringPurity"] for d in recs], dtype=float)
    print(f"\nring assignment purity (fraction of parcel vertices in the winning")
    print(f"Mesulam class):  median {np.median(pur):.2f}   min {pur.min():.2f}   "
          f"<0.6 in {int((pur < 0.6).sum())} parcels")
    g = np.array([d["gradient"] for d in recs])
    rr = np.array([d["rhoRaw"] for d in recs])
    print(f"gradient range   {g.min():.3f} .. {g.max():.3f}")
    print(f"rho raw (native) {rr.min():.3f} .. {rr.max():.3f}   -> normalised 0..1")
    print(f"gradient x rho   Pearson r = {np.corrcoef(g, rr)[0,1]:+.3f}")
    if dropped:
        print(f"\ndropped {len(dropped)} parcels with missing data: {dropped[:8]}")

    # ---- write -------------------------------------------------------------
    (ASSETS / "parcels.json").write_text(json.dumps(recs, indent=1))
    (ASSETS / "palette.json").write_text(json.dumps(pal, indent=1))
    sources = {
        "parcellation": {
            "value": "HCP-MMP1 (Glasser 2016), 360 cortical areas",
            "status": "measured",
            "detail": "fsaverage 164k annot (figshare 5528816/5528819); fsLR 32k dlabel for the gradient.",
        },
        "ring": {
            "value": "Mesulam cortical type, 4 classes",
            "status": "measured",
            "detail": "lh/rh.mesulam.annot, MICA-MNI/micaopen (Paquola et al. 2019), fsaverage 164k. "
                      "Per parcel = modal class over its vertices. Not a proxy: this is the "
                      "Mesulam laminar-differentiation atlas itself.",
        },
        "gradient": {
            "value": "Margulies 2016 principal functional gradient",
            "status": "measured",
            "detail": "neuromaps margulies2016/fcgradient01/fsLR/32k, averaged within parcel in its native space.",
        },
        "rho": {
            "value": "Beliveau 2017 5-HT2A receptor density, [11C]Cimbi-36 PET",
            "status": "measured",
            "detail": "neuromaps beliveau2017/cimbi36/fsaverage/164k (BPnd), averaged within parcel, "
                      f"then min-max normalised across the {len(recs)} parcels "
                      f"(raw {rr.min():.2f}-{rr.max():.2f} in the map's native units). "
                      f"{n_invalid} allocortical parcel(s) with no valid cortical-ribbon signal "
                      "are excluded from the normalisation range and flagged rhoValid=false.",
        },
        "level": {
            "value": "hierarchical level = inverted T1w/T2w myelin",
            "status": "measured",
            "detail": "neuromaps hcps1200/myelinmap/fsLR/32k (HCP S1200 group T1w/T2w ratio), "
                      "averaged within parcel in fsLR 32k using the same Glasser dlabel as the "
                      f"gradient (raw parcel means {mlo:.3f}-{mhi:.3f}), then INVERTED and min-max "
                      "normalised so that high level = low myelin = deep in the hierarchy = INNER "
                      "ring. The sign matters: every prediction and error arrow in the figure is "
                      "drawn from the level difference of its two endpoints.",
        },
        "tau": {
            "value": "intrinsic timescale, MEG",
            "status": "measured",
            "detail": "neuromaps hcps1200/megtimescale/fsLR/4k. Connectome Workbench is "
                      "deliberately not a dependency of this pipeline, and neuromaps' own 4k->32k "
                      "transform shells out to it, so each fsLR 32k vertex instead takes the value "
                      "of the angularly nearest fsLR 4k vertex on the fsLR sphere (pure numpy) and "
                      "the parcel mean is then taken over 32k vertices exactly as for every other "
                      "fsLR map. That resample is nearest-neighbour, not areal -- it is the one "
                      "approximation in this field, and it cannot move a value across a parcel "
                      "boundary by more than the 4k vertex spacing.",
        },
        "stream": {
            "value": "sensory stream, and the colour of every parcel",
            "status": "derived",
            "detail": "Glasser's own 22 cortical divisions grouped into streams, at every ring. "
                      "Colour = that stream's base hue mixed toward transmodal orange by the "
                      "parcel's Mesulam type, so colour is a property of the parcel alone and the "
                      "same parcel is the same colour in Panel A and Panel B. Only 9 of the 195 "
                      "heteromodal/paralimbic parcels sit in a division that names a stream, which "
                      "is why the two inner rings read as near-uniform orange -- that is the "
                      "convergence, not a rendering shortcut.",
        },
        "modality": {
            "value": "visual / auditory / somatomotor (rings 0-1 only)",
            "status": "derived",
            "detail": "Glasser's own 22 cortical divisions grouped into streams. Auditory is a real "
                      "labelled division in HCP-MMP (Early Auditory + Auditory Association), which is "
                      "why HCP-MMP was chosen over Schaefer-Yeo7 (Yeo-7 folds auditory into somatomotor). "
                      "This field drives only the ANGULAR SECTORS, so a stream is a radial slice; it "
                      "is restricted to rings 0-1 because the sectors are shared by those two rings. "
                      "A parcel whose division names no stream falls in the unlabelled sector -- that "
                      "is a gap in Glasser's division names, not a claim about the cortex.",
        },
        "edges": {
            "value": "all three edge layers",
            "status": "assumed",
            "detail": "Ring geometry, the anatomical scaffold, and both functional edge sets are "
                      "schematic. No tractography or functional connectivity was used. Only the "
                      "recruitment ORDER of off-anatomy edges is data-driven (endpoint mean rho).",
        },
        "disruption": {
            "value": "rho x (1 - precision)",
            "status": "assumed",
            "detail": "A restatement of the model assumption, not a measurement or a result.",
        },
        "rhoRank": {
            "value": "percentile rank of rho across the 360 parcels",
            "status": "derived (display scaling)",
            "detail": "The measured 5-HT2A distribution is narrow and left-skewed (interquartile "
                      "range spans only ~14% of the full range), so a linear encoding of rho is "
                      "close to invisible on screen. The figure sizes receptor discs and disruption "
                      "bars by this rank instead. The ORDER is identical to the measured density; "
                      "the SPACING is not. Measured rho and the raw parcel mean are in parcels.json "
                      "and in every tooltip.",
        },
        "tauRank": {
            "value": "percentile rank of tau across the 360 parcels",
            "status": "derived (display scaling)",
            "detail": "Node radius is sized by this rank, not by tau itself. The measured MEG "
                      f"timescale is right-skewed (median {float(np.median(tv_all)):.1f}, max "
                      f"{float(tv_all.max()):.1f} in the map's units), so a linear encoding leaves "
                      "almost every node at the small end of the radius scale. The ORDER is "
                      "identical to the measured timescale; the SPACING is not. The raw value is "
                      "in parcels.json, in every tooltip, and on the generative-model cards.",
        },
    "angle": {
            "value": "angular position within a ring",
            "status": "measured",
            "detail": "Nodes are ordered by their Margulies gradient value, so angle carries real information.",
        },
    }
    (ASSETS / "sources.json").write_text(json.dumps(sources, indent=1))

    # figure.html is opened by double-click, and browsers block fetch() on
    # file:// URLs. The same three payloads are therefore also emitted as a
    # plain script that defines one global. The .json files stay canonical.
    (ASSETS / "data.js").write_text(
        "// Generated by build_assets.py -- do not edit.\n"
        "// Mirrors parcels.json / palette.json / sources.json so figure.html\n"
        "// works from file:// without a web server.\n"
        "window.FIGURE_DATA = "
        + json.dumps({"parcels": recs, "palette": pal, "sources": sources}, indent=1)
        + ";\n"
    )
    print(f"\nwrote assets/parcels.json  ({len(recs)} parcels)")
    print("wrote assets/palette.json, assets/sources.json, assets/data.js")

    if args.skip_render:
        print("\n[8/8] rendering skipped (--skip-render)")
        return

    print("\n[8/8] rendering surfaces")
    meshes = load_fsaverage_meshes()
    by_id = {d["id"]: d for d in recs}

    def stream_colour(k):
        d = by_id.get(k)
        return node_colour(pal, d["ring"], d["stream"]) if d else NEUTRAL_PARCEL

    render_views(meshes, ids, vert, stream_colour, ASSETS / "brain_nodes.png", args.dpi)

    def ring_colour(k):
        d = by_id.get(k)
        return pal["ring"][d["ring"]] if d else NEUTRAL_PARCEL

    render_views(meshes, ids, vert, ring_colour, ASSETS / "brain_rings.png", args.dpi)

    # Ring overlays keep each parcel's own colour and grey out everything else,
    # so highlighting a ring never recodes what a colour means.
    for r in range(4):
        def one(k, r=r):
            d = by_id.get(k)
            if d and d["ring"] == r:
                return node_colour(pal, r, d["stream"])
            return NEUTRAL_PARCEL
        render_views(meshes, ids, vert, one, ASSETS / f"brain_ring_{r}.png", args.dpi)

    def rho_colour(k):
        # Percentile rank, matching how Panel A sizes its receptor discs. A linear
        # ramp on the measured value is nearly flat (see the rhoRank source note).
        d = by_id.get(k)
        return ramp_hex(RHO_RAMP, d["rhoRank"]) if d else NEUTRAL_PARCEL

    render_views(meshes, ids, vert, rho_colour, ASSETS / "brain_rho.png", args.dpi)

    crop_common(
        [ASSETS / "brain_nodes.png", ASSETS / "brain_rings.png", ASSETS / "brain_rho.png"]
        + [ASSETS / f"brain_ring_{r}.png" for r in range(4)]
    )
    print("\ndone.")


if __name__ == "__main__":
    main()
