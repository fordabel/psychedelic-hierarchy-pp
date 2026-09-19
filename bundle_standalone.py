#!/usr/bin/env python3
"""
bundle_standalone.py -- fold figure.html + assets/ into single files.

figure.html loads assets/data.js and seven brain PNGs by relative path, which
is fine on a laptop and useless on a phone. This inlines all of it:

  figure_standalone.html   a complete document. Double-click it, AirDrop it,
                           mail it to yourself. No server, no assets folder.
  figure_artifact.html     the same page as a body-only fragment, for hosts
                           that supply their own <!doctype>/<head>/<body>.

The shaded PNGs are downscaled and palette-quantised on the way in. They are
flat renders with a Lambert term, so 256 colours is visually lossless and takes
8.4 MB down to under half a megabyte. brain_ids.png is inlined byte-exact: it
is a lookup table, not a picture.

Usage:  python bundle_standalone.py [--width 1100] [--colors 256]
"""

import argparse
import base64
import io
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
# Every PNG figure.html loads by relative path. Kept in sync with the page by
# the check below, not by hand: the bundler refuses to run if figure.html
# references a render this list does not carry, and skips any entry the assets
# folder does not have. "brain_nodes" used to be in this list and has not been
# produced since the surfaces were re-rendered; "brain_ids" (the flat
# parcel-id render that drives per-parcel hover) was added to the page and
# never added here, which broke bundling outright.
IMGS = ["brain_rings", "brain_rho", "brain_ids",
        "brain_ring_0", "brain_ring_1", "brain_ring_2", "brain_ring_3"]


def png_data_uri(path, width, colors, exact=False):
    from PIL import Image

    im = Image.open(path).convert("RGBA")
    if not exact:
        if im.width > width:
            im = im.resize((width, round(width * im.height / im.width)), Image.LANCZOS)
        im = im.quantize(colors=colors, method=Image.FASTOCTREE, dither=Image.NONE)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--colors", type=int, default=256)
    args = ap.parse_args()

    html = (HERE / "figure.html").read_text()
    data_js = (ASSETS / "data.js").read_text()

    # 1. the data payload replaces its own <script src>
    tag = '<script src="assets/data.js"></script>'
    if tag not in html:
        raise SystemExit("could not find the data.js script tag in figure.html")
    html = html.replace(tag, "<script>\n" + data_js + "</script>")

    # 2. the brain renders replace the paths the boot code assigns.
    #    brain_ids.png is a LOOKUP TABLE, not a picture: every parcel is one
    #    exact RGB triple and the page decodes it to map pixel -> parcel. It
    #    must not be resized or quantised, or the triples stop matching and
    #    per-parcel hover silently dies.
    referenced = set(re.findall(r"'assets/([A-Za-z0-9_]+)\.png'", html))
    referenced.add("brain_ring_0")             # assigned through the index loop
    missing = referenced - set(IMGS)
    if missing:
        raise SystemExit("figure.html references assets/%s.png, not in IMGS"
                         % ", ".join(sorted(missing)))
    uris = {}
    for n in IMGS:
        src = ASSETS / f"{n}.png"
        if not src.exists():
            raise SystemExit(f"missing asset: {src} - run build_assets.py")
        exact = n == "brain_ids"
        uris[n] = png_data_uri(src, args.width, args.colors, exact=exact)
    total = sum(len(u) for u in uris.values())

    # the four ring overlays are assigned in a loop, by index
    loop_src = "im.src='assets/brain_ring_'+i+'.png';"
    if loop_src not in html:
        raise SystemExit("could not find the ring-overlay loop in figure.html")
    html = html.replace(loop_src, "im.src=IMG['brain_ring_'+i];")

    # everything else is a literal path
    def swap(m):
        name = m.group(1)
        if name not in uris:
            raise SystemExit(f"figure.html references assets/{name}.png, which is not in IMGS")
        return f"IMG[{name!r}]"

    html = re.sub(r"'assets/([A-Za-z0-9_]+)\.png'", swap, html)
    for stray in re.findall(r"'assets/[^']+'", html):
        raise SystemExit(f"unreplaced asset reference: {stray}")

    img_js = ("<script>\n// Brain renders, inlined. Regenerate with bundle_standalone.py.\n"
              "window.IMG={\n" +
              ",\n".join(f'"{n}":"{uris[n]}"' for n in IMGS) + "\n};\n</script>\n")
    html = html.replace("<script>\n" + data_js, img_js + "<script>\n" + data_js)

    out = HERE / "figure_standalone.html"
    out.write_text(html)

    # 3. the same page as a body-only fragment
    frag = html
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title:
        raise SystemExit("figure.html has no <title> to carry into the fragment")
    frag = re.sub(r"^.*?<style>", f"<title>{title.group(1)}</title>\n<style>",
                  frag, count=1, flags=re.S)
    frag = frag.replace("</head>\n<body>", "", 1)
    frag = re.sub(r"</body>\s*</html>\s*$", "", frag, flags=re.S)
    stray = re.search(r"<(?:html|head|body)\b", frag)   # NB: <header> is not <head>
    if stray:
        raise SystemExit(f"fragment still contains document scaffolding: {stray.group(0)}")
    (HERE / "figure_artifact.html").write_text(frag)

    print(f"wrote figure_standalone.html   {out.stat().st_size/1e6:.2f} MB")
    print(f"wrote figure_artifact.html     "
          f"{(HERE/'figure_artifact.html').stat().st_size/1e6:.2f} MB")
    print(f"  ({len(IMGS)} renders at {args.width}px / {args.colors} colours "
          f"= {total*3/4/1e6:.2f} MB of PNG)")


if __name__ == "__main__":
    main()
