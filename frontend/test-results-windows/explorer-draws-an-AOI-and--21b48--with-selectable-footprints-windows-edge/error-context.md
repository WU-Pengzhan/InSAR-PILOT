# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: explorer.spec.ts >> draws an AOI and submits legacy-compatible search filters with selectable footprints
- Location: ..\..\..\..\..\..\wsl$\Ubuntu\Ubuntu\home\griffin\projects\insar-pilot\frontend\e2e\explorer.spec.ts:26:1

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByTestId('data-explorer').getByRole('button', { name: 'Draw AOI', exact: true })

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - toolbar [ref=e5]:
      - generic [ref=e6] [cursor=pointer]:
        - img "InSAR-PILOT logo" [ref=e7]
        - generic [ref=e8]: InSAR-PILOT
        - generic [ref=e9]: NEXT
      - separator [ref=e10]
      - generic [ref=e11]: SAR / InSAR workbench
      - button "24 CPU" [ref=e12] [cursor=pointer]:
        - generic [aria-hidden] [ref=e13]: memory
      - button "Downloads" [ref=e15] [cursor=pointer]:
        - generic [ref=e16]:
          - img [aria-hidden] [ref=e17]: download
          - generic [ref=e18]: Downloads
      - button "Explore" [ref=e19] [cursor=pointer]:
        - generic [ref=e20]:
          - img [aria-hidden] [ref=e21]: travel_explore
          - generic [ref=e22]: Explore
      - button "Hide properties panel" [expanded] [ref=e23] [cursor=pointer]:
        - img [aria-hidden] [ref=e25]: chevron_right
      - button "Change language" [ref=e26] [cursor=pointer]:
        - img [aria-hidden] [ref=e28]: translate
      - button "Toggle theme" [ref=e29] [cursor=pointer]:
        - img [aria-hidden] [ref=e31]: dark_mode
      - generic [ref=e32]:
        - status [ref=e33]: Backend running
        - button "Exit app" [ref=e35] [cursor=pointer]:
          - generic [ref=e36]:
            - img [aria-hidden] [ref=e37]: power_settings_new
            - generic [ref=e38]: Exit app
  - main [ref=e40]:
    - generic [ref=e41]:
      - complementary [ref=e43]:
        - generic [ref=e44]: PROJECT EXPLORER
        - generic [ref=e45]:
          - generic [aria-hidden] [ref=e46]: folder_open
          - paragraph [ref=e47]: Open a project to explore its data and processing history.
          - button "New project" [ref=e48] [cursor=pointer]
        - generic [ref=e51]:
          - button "Downloads" [ref=e52] [cursor=pointer]:
            - generic [ref=e53]:
              - img [aria-hidden] [ref=e54]: download
              - generic [ref=e55]: Downloads
          - button "Files view" [disabled] [ref=e56]:
            - generic [ref=e57]:
              - img [aria-hidden] [ref=e58]: folder
              - generic [ref=e59]: Files view
          - button "Data Library" [ref=e60] [cursor=pointer]:
            - generic [ref=e61]:
              - img [aria-hidden] [ref=e62]: inventory_2
              - generic [ref=e63]: Data Library
      - separator "Resize" [ref=e64]
      - generic [ref=e67]:
        - main [ref=e69]:
          - tablist [ref=e70]:
            - generic [ref=e71]:
              - tab "home" [ref=e72] [cursor=pointer]
              - tab "explore" [selected] [ref=e76] [cursor=pointer]
          - generic [ref=e81]:
            - generic [ref=e82]:
              - generic [ref=e83]:
                - generic [ref=e84]: SAR DATA EXPLORER
                - heading "Find data for your study area" [level=1] [ref=e85]
              - status [ref=e86]: ASF DAAC
            - button "Hide filters" [ref=e87] [cursor=pointer]
            - generic [ref=e90]:
              - generic [ref=e91]:
                - heading "Search criteria" [level=2] [ref=e92]
                - status [ref=e93]: Sentinel-1 · IW · SLC
                - generic [ref=e96] [cursor=pointer]:
                  - generic [ref=e97]:
                    - generic: Mission
                    - generic [ref=e98]:
                      - generic [ref=e99]: SENTINEL-1
                      - combobox "Mission" [ref=e100]: SENTINEL-1
                  - generic [aria-hidden] [ref=e102]: arrow_drop_down
                - group "Sentinel-1 satellites · multi-select" [ref=e103]:
                  - generic [ref=e105]:
                    - checkbox "SENTINEL-1A" [checked] [ref=e106] [cursor=pointer]:
                      - generic [ref=e111]: A
                    - checkbox "SENTINEL-1B" [checked] [ref=e112] [cursor=pointer]:
                      - generic [ref=e117]: B
                    - checkbox "SENTINEL-1C" [checked] [ref=e118] [cursor=pointer]:
                      - generic [ref=e123]: C
                    - checkbox "SENTINEL-1D" [checked] [ref=e124] [cursor=pointer]:
                      - generic [ref=e129]: D
                - generic [ref=e130]:
                  - generic [ref=e134]:
                    - generic: Start date · UTC
                    - textbox "Start date · UTC" [ref=e135]: 2026-06-08
                  - generic [ref=e139]:
                    - generic: End date · UTC
                    - textbox "End date · UTC" [ref=e140]: 2026-09-06
                - generic [ref=e143] [cursor=pointer]:
                  - generic [ref=e144]:
                    - generic: AOI format
                    - generic [ref=e145]:
                      - generic [ref=e146]: BBOX
                      - combobox "AOI format" [ref=e147]: BBOX
                  - generic [aria-hidden] [ref=e149]: arrow_drop_down
                - generic [ref=e153]:
                  - generic: West, south, east, north
                  - textbox "West, south, east, north" [ref=e154]
                - button "Apply AOI to map" [disabled] [ref=e155]:
                  - generic [ref=e156]:
                    - img [aria-hidden] [ref=e157]: center_focus_strong
                    - generic [ref=e158]: Apply AOI to map
                - generic [ref=e161] [cursor=pointer]:
                  - generic [ref=e162]:
                    - generic: Orbit direction · optional
                    - combobox "Orbit direction · optional" [ref=e164]
                  - generic [aria-hidden] [ref=e166]: arrow_drop_down
                - generic [ref=e170]:
                  - generic: Relative orbit · optional
                  - spinbutton "Relative orbit · optional" [ref=e171]
                - generic [ref=e174] [cursor=pointer]:
                  - generic [ref=e175]:
                    - generic: Polarization · optional
                    - combobox "Polarization · optional" [ref=e177]
                  - generic [aria-hidden] [ref=e179]: arrow_drop_down
                - generic [ref=e180]:
                  - button "Search SAR data" [ref=e181] [cursor=pointer]:
                    - generic [ref=e182]:
                      - img [aria-hidden] [ref=e183]: search
                      - generic [ref=e184]: Search SAR data
                  - button "Reset filters" [ref=e185] [cursor=pointer]
              - generic [ref=e188]:
                - generic [ref=e189]:
                  - button "Fit coverage" [ref=e191] [cursor=pointer]
                  - generic [ref=e194]:
                    - generic:
                      - generic [ref=e195]:
                        - button "Zoom in" [ref=e196] [cursor=pointer]: +
                        - button "Zoom out" [ref=e197] [cursor=pointer]: −
                      - generic [ref=e198]:
                        - link "Leaflet" [ref=e199] [cursor=pointer]:
                          - /url: https://leafletjs.com
                        - text: "| Tiles © Esri"
                - generic [ref=e204]:
                  - generic [ref=e205]:
                    - generic [ref=e206]: Download settings
                    - button "Refresh download readiness" [ref=e207] [cursor=pointer]:
                      - img [aria-hidden] [ref=e209]: refresh
                  - generic [ref=e210]:
                    - generic [ref=e211]: aria2c · missing
                    - generic [ref=e213]: Earthdata · configured
                  - code [ref=e215]: /tmp/pilot-picker-e2e-dsiqxo3y/library
                  - generic [ref=e216]: DEM · GDAL available
                  - button "Expand \"Download executable\"" [ref=e220] [cursor=pointer]:
                    - generic [ref=e221]: Download executable
                    - generic [aria-hidden] [ref=e224]: keyboard_arrow_down
            - generic [ref=e225]:
              - heading "Search results · 0" [level=2] [ref=e227]
              - paragraph [ref=e228]: Choose a date range and draw or import an AOI, then search.
              - generic [ref=e229]:
                - button "Selected scenes (0)" [ref=e230] [cursor=pointer]
                - button "Download only" [disabled] [ref=e233]:
                  - generic [ref=e234]:
                    - img [aria-hidden] [ref=e235]: download
                    - generic [ref=e236]: Download only
                - button "Create project from selection" [disabled] [ref=e237]
            - button "Expand \"Network settings\"" [ref=e242] [cursor=pointer]:
              - generic [ref=e243]: Network settings
              - generic [aria-hidden] [ref=e246]: keyboard_arrow_down
        - separator "Resize" [ref=e247]
        - complementary [ref=e250]:
          - generic [ref=e251]:
            - generic [ref=e252]: INSPECTOR
            - button "Collapse properties panel" [ref=e253] [cursor=pointer]:
              - img [aria-hidden] [ref=e255]: chevron_right
          - heading "Object details" [level=3] [ref=e256]
          - tablist [ref=e257]:
            - generic [ref=e258]:
              - tab "Properties" [selected] [ref=e259] [cursor=pointer]
              - tab "QC" [ref=e263] [cursor=pointer]
              - tab "History" [ref=e267] [cursor=pointer]
          - generic [ref=e271]:
            - generic [aria-hidden] [ref=e272]: touch_app
            - paragraph [ref=e273]: Select a step, run or artifact to inspect its properties and provenance.
  - contentinfo [ref=e274]:
    - generic [ref=e275]:
      - generic [ref=e277]: Local engine
      - separator [ref=e278]
      - generic [ref=e279]: 0 processing jobs
      - button "Jobs" [ref=e280] [cursor=pointer]
      - button "Downloads" [ref=e283] [cursor=pointer]:
        - generic [ref=e284]:
          - img [aria-hidden] [ref=e285]: download
          - generic [ref=e286]: Downloads
      - generic [ref=e287]: Unassigned · Migration preview
```