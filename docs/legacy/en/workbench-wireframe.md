> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# Next-generation Workbench wireframe

This document fixes the low-fidelity structure for the first Workbench shell and Search workspace increment. The increment validates information hierarchy, layout switching, and the Qt Model/View boundary only. It does not connect network search, download, Catalog, import, processing, or visualization.

## Normal (1440 × 900 baseline, usable at 1366 × 768)

```text
┌ InSAR-PILOT Workbench ───────────────────────────────────────────────┐
│ Search                                                              │
├──────────────────────┬───────────────────────────────────────────────┤
│ Mission              │ Map                                           │
│ Product type         │                                               │
│ Start / End date     │                                               │
│ AOI                  │                                               │
│ [Advanced filters ▸] ├───────────────────────────────────────────────┤
│                      │ Search results                                 │
│ [ Search ]           │ QTableView / QAbstractTableModel               │
└──────────────────────┴───────────────────────────────────────────────┘
```

- The filter pane targets about 24% of the available width without a fixed width.
- Map and results use an approximate 58:42 height split.
- Inspector, Tasks, and Logs start hidden and are opened from the View menu.
- Advanced filters start collapsed.

## Maximized

```text
┌ InSAR-PILOT Workbench ─────────────────────────────────────────────────────┐
│ Search                                                                    │
├────────────────────────┬───────────────────────────────────────────────────┤
│ Mission                │ Map                                               │
│ Product type           │                                                   │
│ Start / End date       │                                                   │
│ AOI                    │                                                   │
│ [Advanced filters ▸]   │                                                   │
│                        ├───────────────────────────────────────────────────┤
│ [ Search ]             │ Search results                                    │
└────────────────────────┴───────────────────────────────────────────────────┘
```

- Maximizing adds space to map and results without adding default information.
- The filter pane remains usable; map and results use an approximate 64:36 height split.
- Dock visibility never changes automatically with the window mode.

## State boundaries

- The first increment delivers a static empty state. Search emits a view intent but performs no query.
- The table model can later receive loading, data, and error states without importing provider types.
- Inspector and the Tasks/Logs drawer are structural placeholders only.
- Search, selection, download, and task state must never trigger visualization.

## Capability-driven form

The fourth phase preserves the wireframe and both layout modes while replacing the source of control data:

- Mission, Product type, Platform, and Advanced filters are injected from the production Provider Registry.
- Mission changes rebuild product, platform, and filter options; Product type or Platform changes retain only conditions supported by at least one schema.
- Unsupported filter rows are hidden, while Advanced filters remain collapsed by default.
- An empty Registry shows “no providers available” and disables Search instead of inventing placeholder missions.
- Context changes cancel active search and clear stale results without starting a query or visualization.
