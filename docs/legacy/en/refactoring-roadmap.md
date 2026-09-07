> LEGACY / HISTORICAL EVIDENCE. Not an active architecture specification.

# Next-generation refactoring roadmap and GUI constraints

This document defines the target scope, GUI constraints, and implementation order for the next InSAR-PILOT generation. It is a development target, not a description of features already delivered by v1.2.0. Refer to the [User Guide](../../en/user-guide.md) and [Architecture](architecture.md) for current behavior.

## 0. Current status and active milestone

The Workbench shell, normalized search domain, capability-driven form, and Sentinel-1 remote search now form the baseline for the next increment. The production Registry still contains ASF Sentinel-1 only; NISAR RSLC and ALOS search-only remain domain contracts exercised with fake providers.

The active milestone is now **Sentinel-1 / NISAR data integration**: canonical local products and asset references, read-only import, a shared Data Catalog, compatibility checks, and workflow eligibility. It does not mean cross-mission interferometric pairing or completed NISAR ISCE3 processing. The detailed acceptance rules, real-data paths, and sequential VSCode Codex prompts are maintained in the Chinese [milestone guide](../sentinel-nisar-data-integration.md).

## 1. Refactoring rules

- Preserve the working Sentinel-1 + ISCE2 TOPS Stack path.
- Build the new Workbench shell alongside the current window and do not switch the default before visual and interaction acceptance.
- Keep processing and provider logic outside Qt widgets.
- Standardize logical products and asset references, not physical file formats.
- Visualization is an explicit user-invoked function. Import, selection, download, and task completion must not render automatically.
- Implement only the mission and workflow scope that has explicit acceptance criteria.

## 2. Search-phase mission scope (historical baseline)

| Mission | Next milestone | Out of scope |
|---|---|---|
| Sentinel-1A/B/C/D | SLC search and normalized remote results | Rewriting the existing ISCE2 processing chain |
| NISAR | RSLC search and normalized remote results | GSLC and full InSAR processing in this milestone |
| ALOS family | Search integration and result display only | SLC import and ISCE2/ISCE3 processing |

Sentinel-1D must have an explicit platform mapping. If the upstream provider or dependency does not support it, return a clear unsupported status rather than silently broadening the query to all Sentinel-1 platforms.

ALOS satellite, product-level, and provider support must be captured in a separate verified matrix before implementation. Search results must not be advertised as processable SLCs without a validated importer and backend capability.

## 3. GUI redesign constraints

The first release exposed too much text and too many controls, while independent fixed sizes and stretch policies caused clipping, crowding, and poor resizing. The next GUI must use progressive disclosure and centralized layout policy.

### 3.1 Information hierarchy

- One primary job and at most two primary actions per workspace.
- Move long guidance to tooltips, contextual help, or empty states.
- Collapse advanced filters, full paths, commands, diagnostics, provider payloads, and logs by default.
- Display each status once instead of repeating it across toolbar, cards, sidebar, and body.
- Visualization is never a default panel or automatic action.

### 3.2 Search workbench

```text
Project / Search / Download / Task status
├── Search filters
└── Map
    └── Search results
Tasks / Errors / Logs (on demand)
```

The default filter surface contains mission, product type, date, AOI, and the most common filters. Orbit, polarization, frequency, and provider-specific settings live under Advanced filters. Product details use a temporary drawer or inspector.

### 3.3 Layout modes

Maintain two accepted layout strategies instead of independent widget-specific resizing:

1. **Normal**: designed at 1440 × 900 and usable at 1366 × 768.
2. **Maximized**: gives additional space to the map and results without exposing more default information.

A centralized breakpoint switches between the modes. Major containers use consistent size policies, minimum sizes, and stretch factors. Only icons, status marks, and a small number of primitive controls may use fixed sizes. Validate both modes at 100%, 125%, and 150% DPI.

### 3.4 Interaction performance

- Common click targets are at least 36 px high; compact table rows are at least 28 px.
- Splitter handles and scrollbars need reliable hit areas.
- Unfocused combo and spin controls must not steal page-wheel events.
- Coalesce high-frequency wheel and mouse events.
- Batch map-marker and model updates.
- Use Qt Model/View for result sets; do not create one QWidget per cell.
- Never parse large SAFE/HDF5 files, download, render, or invoke GDAL/ISCE on the GUI thread.
- Do not rebuild an entire model while scrolling, zooming, or dragging a splitter.

### 3.5 Visual acceptance gate

Submit a low-fidelity wireframe before implementation. After implementation, inspect screenshots for Normal/Maximized, 100%/125%/150% DPI, Chinese/English, and empty/loading/data/error states. Also test long paths, long names, dock transitions, maximize/restore, continuous scrolling, map zoom, and splitter dragging. Offscreen widget tests alone do not constitute GUI acceptance.

## 4. Search framework

```text
GUI Workbench
→ Search Application Service
→ SearchRequest / RemoteSARProduct
→ Provider Registry
   ├── ASF Sentinel-1
   ├── NISAR
   └── ALOS search-only
```

```python
class SARSearchProvider(Protocol):
    descriptor: ProviderDescriptor

    def supports(self, request: SearchRequest) -> SupportReport: ...
    def search(self, request: SearchRequest, context: SearchContext) -> SearchPage: ...
```

The common request contains mission, platforms, product type, time range, AOI, orbit, polarization, frequency, and pagination. Provider-specific settings remain namespaced and hidden from the default form.

`RemoteSARProduct` represents a provider result. It is not a Catalog `SLCProduct`. Provider SDK objects must not enter the GUI.

Search must be cancellable, stale responses must not replace newer results, and provider failures must map to common authentication, network, rate-limit, unsupported, invalid-query, and provider-error types.

## 5. Search-phase implementation order (historical baseline)

1. Preserve existing tests and characterize the current Sentinel-1 ASF search.
2. Approve Normal and Maximized wireframes using realistic Chinese/English text and paths.
3. Add the new application/search, domain/search, providers/sar, ui/workbench, ui/models, and ui/features/search skeletons without moving current ISCE2 services.
4. Define the common search models and provider registry.
5. Wrap the existing ASF provider, then add explicit Sentinel-1A/B/C/D mapping, NISAR RSLC, and ALOS search-only adapters.
6. Build the Model/View search workspace with shared map/table selection, cancellation, controlled result limits, and collapsed advanced/details/task areas.
7. Complete the screenshot and interaction acceptance matrix while keeping the legacy GUI and ISCE2 path operational.

## 6. Search-phase acceptance baseline

The framework-and-search milestone is complete only when:

1. The new Workbench does not depend on the current `MainWindow` widget aliases or controllers reaching directly into the window.
2. Sentinel-1A/B/C/D, NISAR RSLC, and ALOS use the same `SearchRequest` and normalized result model.
3. NISAR GSLC is absent from the UI and rejected by the API.
4. ALOS results expose no Run/Process action or processing capability.
5. Provider-native objects never reach the GUI.
6. Search cancellation and stale-request protection work.
7. Map, table, and inspector selection remain synchronized.
8. Visualization never starts automatically.
9. The layout/DPI/language visual matrix passes.
10. Existing tests, lint, type checks, and the current ISCE2 workflow remain operational.

Only after this milestone should development proceed to unified downloads, Canonical SLC/RSLC import, the Data Catalog, and processing backend refactoring.

## 7. Capability-driven Search Framework

The fourth phase stabilizes the provider capability contract before adding production providers:

- `SearchCapability` describes missions, product types, platforms, cross-mission filters, and pagination limits.
- `ProviderDescriptor` continues to describe provider-owned SEARCH/DOWNLOAD/PROCESSING capabilities; the Search Registry is not a processing-backend registry.
- The Workbench form owns no Sentinel, NISAR, or ALOS option lists. Every option is projected from the production Registry through the Application Service.
- Descriptor-invalid combinations fail before background task submission; runtime provider availability remains a background `supports` check.
- The production Registry remains ASF Sentinel-1 only in this phase. NISAR RSLC and ALOS search-only are verified with fake providers and do not enter production as placeholders.

Pagination enters the schema and request validation, while pagination controls, downloads, Catalog, import, processing, and visualization remain out of scope.

## 8. Active milestone: Sentinel-1 / NISAR data integration

The active increment standardizes the local data contract before implementing a full ISCE3 backend:

```text
Sentinel ZIP/SAFE → Sentinel1SafeReader ─┐
                                         ├→ LocalSARProduct / AssetRef
NISAR RSLC HDF5 → NisarRslcReader ──────┘
                                                     ↓
                                              Project Data Catalog
                                                     ↓
                                  Compatibility / Workflow Eligibility
```

Source data remains read-only and is not converted into a common physical format. File assets and HDF5 subdatasets share one asset-reference contract. Sentinel TOPS and NISAR tasks are projected from recipe/capability descriptors and must not leak into each other. Until an executable ISCE3 backend is available, the Workbench must not expose a false NISAR Run action. Visualization remains explicitly user-invoked.

After this milestone passes real-data and regression acceptance, the next milestone may rebuild the NISAR ISCE3 RIFG backend around the preserved RSLC/RIFG golden evidence.
