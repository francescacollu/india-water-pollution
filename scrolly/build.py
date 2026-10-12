"""
Build the scrollytelling page from story.md.

    python build.py            draft build: [[note: ...]] boxes are visible
    python build.py --final    final build: notes removed, warnings for loose ends
    python build.py --watch    rebuild automatically every time you save a file

Output (in dist/):
    standalone.html   a complete web page — open it in a browser to preview
    embed.html        the same story without <html>/<body>, for pasting into a
                      WordPress "Custom HTML" block

How it works
------------
1. Read story.md: the settings at the top (between ---), then the text.
2. Turn the text into HTML. Plain Markdown becomes paragraphs/headings;
   [[...]] lines become images, videos, notes, and scrolly sections.
3. Glue together, inside ONE file: the HTML, src/styles.css, the data in
   src/data/, and the JavaScript in src/ (scroll engine + graphics).

No extra Python packages are needed.
"""

import html
import json
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
DIST = HERE / "dist"
STORY = HERE / "story.md"
ASSETS = HERE / "assets"

D3_URL = "https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"

# JavaScript files, in the order they must load.
JS_FILES = ["graphics/*.js", "scrolly.js"]

SHORTCODE = re.compile(r"^\[\[\s*(/?[\w-]+)\s*(:?)(.*?)\]\]$")
ATTR = re.compile(r'([\w-]+)(?:="([^"]*)")?')


class Html(str):
    """A piece of finished HTML (as opposed to a line of Markdown)."""


warnings = []


# ---------------------------------------------------------------------------
# Small Markdown converter (just the parts a story needs)
# ---------------------------------------------------------------------------

def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def markdown(lines):
    out = []
    blocks = re.split(r"\n\s*\n", "\n".join(lines).strip())
    for block in filter(None, (b.strip() for b in blocks)):
        rows = block.splitlines()
        heading = re.match(r"^(#{2,4})\s+(.*)", block)
        if heading and len(rows) == 1:
            level, text = len(heading.group(1)), heading.group(2)
            out.append(f'<h{level} id="{slug(text)}">{inline(text)}</h{level}>')
        elif all(r.startswith(">") for r in rows):
            text = " ".join(r.lstrip("> ").strip() for r in rows)
            out.append(f"<blockquote><p>{inline(text)}</p></blockquote>")
        elif all(r.startswith("- ") for r in rows):
            out.append("<ul>" + "".join(f"<li>{inline(r[2:])}</li>" for r in rows) + "</ul>")
        elif block.startswith("<"):
            out.append(block)  # raw HTML passes through untouched
        else:
            out.append(f"<p>{inline(' '.join(rows))}</p>")
    return "\n".join(out)


def render_items(items):
    """Render a list mixing Markdown lines and finished Html pieces."""
    out, buf = [], []
    for item in items:
        if isinstance(item, Html):
            out.append(markdown(buf))
            buf = []
            out.append(item)
        else:
            buf.append(item)
    out.append(markdown(buf))
    return "\n".join(filter(None, out))


# ---------------------------------------------------------------------------
# [[shortcodes]]
# ---------------------------------------------------------------------------

def attrs_of(text):
    return {k: (v if v is not None else True) for k, v in ATTR.findall(text)}


def media_figure(kind, a):
    src = a.get("src", "")
    size = a.get("size", "normal")
    cls = {"wide": " fo-iw-wide", "full": " fo-iw-bleed"}.get(size, "")
    if not src:
        warnings.append(f"{kind} with empty src (caption: {a.get('caption', '')!r})")
        inner = f'<div class="fo-iw-media-missing">{kind.capitalize()} goes here</div>'
    elif kind == "image":
        inner = f'<img src="{html.escape(src)}" alt="{html.escape(a.get("alt", a.get("caption", "")))}" loading="lazy">'
    else:
        poster = f' poster="{html.escape(a["poster"])}"' if a.get("poster") else ""
        flags = " autoplay muted loop playsinline" if a.get("autoplay") else " controls playsinline"
        inner = f'<video src="{html.escape(src)}"{poster}{flags} preload="metadata"></video>'
    if src.startswith("assets/"):
        warnings.append(f"{src} is a local file — upload it to WordPress and use the full URL before handing over")
    caption = inline(a.get("caption", ""))
    credit = f' <span class="fo-iw-credit">{inline(a["credit"])}</span>' if a.get("credit") else ""
    figcap = f"<figcaption>{caption}{credit}</figcaption>" if caption or credit else ""
    return Html(f'<figure class="fo-iw-media{cls}">{inner}{figcap}</figure>')


def render_scrolly(s):
    steps = "\n".join(
        f'<div class="fo-iw-step" data-view="{html.escape(view)}">'
        f'<div class="fo-iw-step-card">{render_items(items)}</div></div>'
        for view, items in s["steps"]
    )
    return Html(
        f'<section class="fo-iw-scrolly fo-iw-scrolly--{s["layout"]} fo-iw-bleed" data-graphic="{s["graphic"]}">\n'
        f'<div class="fo-iw-graphic-wrap"><figure class="fo-iw-graphic"></figure></div>\n'
        f'<div class="fo-iw-steps">\n{steps}\n</div>\n</section>'
    )


def parse_body(text, meta, final):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)   # drop comments
    items, scrolly = [], None

    def target():
        return scrolly["steps"][-1][1] if scrolly and scrolly["steps"] else items

    for n, line in enumerate(text.splitlines(), 1):
        m = SHORTCODE.match(line.strip())
        if not m:
            target().append(line)
            continue
        name, colon, rest = m.group(1), m.group(2), m.group(3).strip()
        a = attrs_of(rest)

        if name == "scrolly":
            scrolly = {"graphic": a.get("graphic", "placeholder"),
                       "layout": a.get("layout", meta.get("default_layout", "overlay")),
                       "steps": []}
        elif name == "step":
            if not scrolly:
                sys.exit(f"story.md line {n}: [[step]] outside a [[scrolly]] block")
            scrolly["steps"].append((a.get("view", ""), []))
        elif name == "/scrolly":
            items.append(render_scrolly(scrolly))
            scrolly = None
        elif name == "note":
            if final:
                continue
            target().append(Html(f'<p class="fo-iw-note">{inline(rest)}</p>'))
        elif name in ("image", "video"):
            target().append(media_figure(name, a))
        else:
            sys.exit(f"story.md line {n}: unknown block [[{name}]]")

    if scrolly:
        sys.exit("story.md: a [[scrolly]] block is missing its [[/scrolly]]")
    return render_items(items)


def parse_front_matter(raw):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, flags=re.S)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if line.strip() and not line.lstrip().startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, raw[m.end():]


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------

def hero(meta):
    style = ""
    if meta.get("hero_image"):
        style = f' style="background-image:url(\'{html.escape(meta["hero_image"])}\')"'
    caption = f'<div class="fo-iw-hero-caption">{inline(meta["hero_caption"])}</div>' if meta.get("hero_caption") else ""
    return (
        f'<header class="fo-iw-hero fo-iw-bleed"{style}><div class="fo-iw-hero-inner">'
        f'<h1>{inline(meta.get("title", ""))}</h1>'
        f'<p class="fo-iw-dek">{inline(meta.get("dek", ""))}</p>'
        f'<p class="fo-iw-byline">{inline(meta.get("author", ""))} · {inline(meta.get("date", ""))}</p>'
        f"</div>{caption}</header>"
    )


def build(final=False):
    warnings.clear()
    meta, body_md = parse_front_matter(STORY.read_text(encoding="utf-8"))
    body = parse_body(body_md, meta, final)

    css = (SRC / "styles.css").read_text(encoding="utf-8")
    js = ["window.FOIW = window.FOIW || { graphics: {} };"]
    for pattern in JS_FILES:
        for f in sorted(SRC.glob(pattern)):
            js.append(f"/* ---- {f.relative_to(SRC).as_posix()} ---- */\n" + f.read_text(encoding="utf-8"))

    data_file = SRC / "data" / "india_states.json"
    data = data_file.read_text(encoding="utf-8") if data_file.exists() else "{}"
    data = data.replace("</", "<\\/")   # a "</script>" inside the data would end the tag early

    fragment = "\n".join([
        "<!-- India water story — generated by build.py, do not edit by hand -->",
        '<div class="fo-iw" id="fo-iw">',
        f"<style>\n{css}\n</style>",
        hero(meta),
        f'<article class="fo-iw-body">\n{body}\n</article>',
        f'<script type="application/json" id="fo-iw-data">{data}</script>',
        f'<script src="{D3_URL}"></script>',
        "<script>\n(function () {\n" + "\n".join(js) + "\n})();\n</script>",
        "</div>",
    ])

    DIST.mkdir(exist_ok=True)
    (DIST / "embed.html").write_text(fragment, encoding="utf-8")
    page = (SRC / "template.html").read_text(encoding="utf-8")
    page = page.replace("{{TITLE}}", html.escape(meta.get("title", ""))).replace("{{FRAGMENT}}", fragment)
    (DIST / "standalone.html").write_text(page, encoding="utf-8")
    if ASSETS.exists():
        shutil.copytree(ASSETS, DIST / "assets", dirs_exist_ok=True)

    size = (DIST / "embed.html").stat().st_size / 1024
    print(f"[{time.strftime('%H:%M:%S')}] Built dist/standalone.html and dist/embed.html ({size:.0f} KB)"
          + (" - FINAL" if final else " - draft"))
    if final:
        for w in warnings:
            print("  warning:", w)


def watch():
    def snapshot():
        files = [STORY, *SRC.rglob("*")] + (list(ASSETS.rglob("*")) if ASSETS.exists() else [])
        return {f: f.stat().st_mtime for f in files if f.is_file()}

    print("Watching story.md and src/ - press Ctrl+C to stop.")
    last = None
    while True:
        now = snapshot()
        if now != last:
            try:
                build()
            except SystemExit as e:   # show story.md mistakes without stopping the watcher
                print("  error:", e)
            last = now
        time.sleep(1)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        build(final="--final" in sys.argv)
