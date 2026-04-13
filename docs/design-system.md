# Design System

## Principles

- scientific, calm, explicit
- readable on WSL desktop displays
- advanced-user transparency by default
- novice-friendly primary flow, expert controls tucked into collapsible sections

## Theme Policy (Light-Only)

- The default product direction is a light professional desktop style for scientific/GIS/engineering use.
- Dark theme guidance is out of scope for the default UI direction.
- If an optional theme is ever added later, light remains the baseline design reference and QA target.

## Layout System

### Shell

- top project header
- left workflow navigation
- center task page
- right summary sidebar
- bottom collapsible console

### Spacing

- shell gap: `12-14px`
- card padding: `14-16px`
- form row spacing: `10px`
- button group spacing: `8-12px`

## Color Roles

- app background: very light neutral gray
- surface: white
- secondary surface: pale gray
- border: cool light gray
- accent: restrained blue / steel-blue
- text primary: dark neutral
- text secondary: muted gray

Suggested baseline tokens:

- background: `#f4f6f9`
- surface: `#ffffff`
- secondary surface: `#eef2f6`
- border: `#cfd7e3`
- primary text: `#202734`
- secondary text: `#5e6a7d`
- accent: `#2f5f94`

### Status Colors

- neutral: muted slate
- ready/success: restrained green
- running: steel-blue
- warning: amber-brown
- failed/error: muted rust red

## Typography

- default Qt/system sans
- increased base size for WSL readability
- hierarchy by weight and contrast, not decorative fonts

## Core Components

### Status Badge

- short text only
- one semantic tone
- used in header, navigation, cards, and run states

### Summary Card

- title
- key value
- supporting sentence
- optional badge

Used for:

- source readiness
- AOI summary
- swath selection
- reference status
- processing plan
- outputs/preview state

### Path Picker Row

- editable path field
- browse action
- optional contextual secondary action such as `Use Selected Output`

### Collapsible Section

- hidden by default for advanced controls
- used for runtime settings, expert controls, and visualization details

### Preview Panel

- original-size image in scroll area
- metadata pane below
- reusable for Results-first preview flows

## Interaction Patterns

### Navigation

- page names reflect user tasks
- badges communicate readiness, not just errors

### Error Handling

- blocking validation errors use modal dialogs
- ongoing command context stays in log console
- pages should not hide the failing command/log path

### Empty States

Each empty state should explain:

- what is missing
- why it matters
- the next primary action

## Styling Notes

- avoid bright neon colors
- avoid crowded form density
- keep card and control radii moderate
- keep hover/focus states visible for keyboard use

## Implementation Notes

- prefer reusable widget classes over one-off layouts inside `MainWindow`
- avoid page widgets owning backend orchestration logic directly
- preserve service-layer APIs while iterating on presentation
- keep practitioner workflow navigation and Results-integrated visualization unchanged while styling evolves
