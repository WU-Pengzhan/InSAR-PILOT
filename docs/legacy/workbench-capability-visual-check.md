> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# Workbench capability-driven Search visual check

Date: 2026-08-31

Qt's offscreen platform was used with the production light theme. Captures were
inspected at original device-pixel size and kept in `/tmp` rather than committed
as product assets. No network request or product visualization was started.

## Layout and DPI matrix

The Cartesian product of the following settings passed geometry assertions:

- Layout: Normal at 1366×768; Maximized policy at 1920×1080.
- Locale: English and Chinese.
- Scale: 100%, 125%, and 150%.

All 12 cases kept the filter panel above its minimum size, map and results areas
usable, Search visible, and Advanced filters and Inspector collapsed. The
production Registry showed only Sentinel-1, SLC, and four platforms (A/B/C/D).

## State and capability checks

| Case | Layout / locale / scale | Result |
| --- | --- | --- |
| Empty | Normal / English / 100% | Pass |
| Loading | Normal / Chinese / 125% | Pass; Cancel visible |
| Results | Maximized / English / 150% | Pass; table and markers aligned |
| No results | Maximized / Chinese / 100% | Pass |
| Error | Normal / English / 150% | Pass; message wraps |
| Fake NISAR | Normal / Chinese / 125% | Pass; RSLC, NISAR platform, frequency row only |
| Fake ALOS | Maximized / English / 150% | Pass; SLC, ALOS-2 platform, no processing controls |

The fake NISAR and ALOS captures expanded Advanced filters only after confirming
that the section started collapsed. Their providers were test-only descriptors
and were never added to the production Registry.

Window-manager chrome, continuous splitter dragging, and restore transitions
still require a final interactive check on the target WSLg display. This does
not affect the offscreen geometry and state acceptance recorded here.
