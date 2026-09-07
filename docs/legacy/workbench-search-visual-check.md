> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# Workbench Search visual check

Date: 2026-08-31

The Search workspace was captured with Qt's offscreen platform after applying
the production light theme. The temporary PNGs were inspected at their original
device-pixel size; they are intentionally not committed as product assets.

In addition to the five state captures below, a 12-case geometry sweep covered
the Cartesian product of Normal/Maximized, English/Chinese, and 100/125/150%
scale. Every case passed minimum-size, primary-action visibility, and usable
map/results-area assertions.

| State | Layout | Locale | Scale | Logical size | Captured pixels | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Empty | Normal | English | 100% | 1366×768 | 1366×768 | Pass |
| Loading | Normal | Chinese | 125% | 1440×900 | 1800×1125 | Pass |
| Results | Maximized | English | 150% | 1920×1080 | 2880×1620 | Pass |
| No results | Maximized | Chinese | 100% | 1920×1080 | 1920×1080 | Pass |
| Error | Normal | English | 150% | 1366×768 | 2049×1152 | Pass |

Checks performed for every capture:

- Mission, product type, date range, AOI, and Search remain visible.
- Advanced filters and Inspector remain collapsed.
- Filter labels and actions are not clipped in either locale.
- Map and result-state/table areas retain usable space without fixed-size conflicts.
- Loading shows its progress indicator and Cancel action; the other four states
  show only their relevant result content.
- The results capture shows a single batch of table rows and matching footprint
  markers at 150% scale.
- No search, selection, or state transition opened a visualization surface.

The offscreen maximized checks apply the centralized Maximized layout policy to
a 1920×1080 logical window. Window-manager chrome and monitor placement require
a later interactive acceptance pass on the target WSL display.
