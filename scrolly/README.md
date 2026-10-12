# India water story — scrollytelling page

## The daily loop

1. Write in **`story.md`** (instructions for the special `[[...]]` blocks are at its top).
2. Run, from this `scrolly/` folder:
   ```
   python build.py --watch
   ```
   It rebuilds every time you save.
3. Preview: in a second terminal run `python -m http.server 8765 -d dist`,
   then open <http://localhost:8765/standalone.html> and refresh after each save.
   (Double-clicking `dist/standalone.html` also works for most things.)

When the data changes (CSV/GeoJSON): `python prepare_data.py`, then build again.

## What each file does

| File | What it is | Do you edit it? |
|---|---|---|
| `story.md` | All the text, images, videos, and which chart each scrolly section uses | **Yes, all the time** |
| `build.py` | Turns `story.md` + `src/` into the final HTML | Rarely |
| `prepare_data.py` | Shrinks the map (1 MB → 129 KB) and attaches the sewage numbers | When data changes |
| `src/styles.css` | Look and layout. Colours and fonts are at the top (section 1) | Sometimes |
| `src/scrolly.js` | Scroll engine: "which card is in the middle → tell the chart" | Rarely |
| `src/graphics/*.js` | One file per chart. Each one lists its "views" at the top | When adding charts |
| `src/template.html` | Page shell used only for the standalone version | Rarely |
| `assets/` | Photos/videos while drafting (copied into `dist/assets/`) | Yes |
| `dist/` | **Generated output. Never edit; it's overwritten on every build** | No |

## How a scrolly section works

```
[[scrolly graphic="sewage-map" layout="side"]]
[[step view="treated"]]
Text...
[[/scrolly]]
```

- `graphic=` picks a file in `src/graphics/`.
- Each `view=` is a state of that chart. When the card reaches the middle of the
  screen, `scrolly.js` calls the chart's `update("treated")`.
- `layout=` is `overlay` (chart full-screen, cards on top) or `side`
  (text left, chart right). Leave it out to use `default_layout` from the top of
  `story.md`. On phones, `side` automatically becomes `overlay`.
- If a chart doesn't exist yet, use `graphic="placeholder"`. It just shows the view
  name, so you can plan the steps now.

## Adding a new chart

1. Copy `src/graphics/placeholder.js` to e.g. `src/graphics/groundwater.js`.
2. Change the name in `FOIW.graphics["..."]`, then draw inside `el` and react to views in `update(view)`.
3. In `story.md`, switch `graphic="placeholder"` to `graphic="groundwater"`.

D3 (v7) is loaded for charts. If a chart needs new data, add it in `prepare_data.py`.

## Handing over (final build)

```
python build.py --final
```

This removes all `[[note: ...]]` boxes and lists loose ends, such as empty image
slots or images still pointing to local `assets/` files. Before handover, upload
photos/videos to the WordPress media library and put their full URLs in `story.md`.

---

## Note for Fair Observer IT

The story is one self-contained file. Everything is inline except D3, which loads from
`cdn.jsdelivr.net`. All CSS is scoped under `.fo-iw`, and all JS is wrapped
(one global: `window.FOIW`).

There are two ways to publish it:

- **A. Paste `dist/embed.html` into a "Custom HTML" block** (preferred). Sections break
  out of the content column to full width. Requirements:
  - `<script>` tags must not be stripped. This needs `unfiltered_html`/admin, or a plugin.
  - No ancestor of the block may have `overflow: hidden/auto` or `transform`.
    Either one breaks `position: sticky`, which the scrolly sections rely on.
    `overflow-x: clip` is fine.
  - A full-width page template (no sidebar) is preferred.
- **B. Host `dist/standalone.html` as its own page** (e.g. a subfolder on the server) and
  link to it, or open it full-screen.

**Avoid a plain auto-height `<iframe>`.** Inside an iframe that grows to fit its content,
sticky graphics never stick, so the scrollytelling stops working. An iframe only works
at a fixed `100vh` height with internal scrolling, which feels worse for readers.
