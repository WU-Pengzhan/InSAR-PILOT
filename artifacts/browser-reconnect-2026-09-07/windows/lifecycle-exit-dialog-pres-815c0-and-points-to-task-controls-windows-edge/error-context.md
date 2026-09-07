# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: lifecycle.spec.ts >> exit dialog preserves active jobs and points to task controls
- Location: ..\..\..\..\..\..\wsl$\Ubuntu\Ubuntu\home\griffin\projects\insar-pilot\frontend\e2e\lifecycle.spec.ts:5:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('download-jobs')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByTestId('download-jobs') with timeout 5000ms
  - waiting for getByTestId('download-jobs')

```

```yaml
- banner:
  - toolbar:
    - img "InSAR-PILOT logo"
    - text: InSAR-PILOT
    - separator
    - text: No project open
    - button "Environment"
    - button "Downloads"
    - button "Explore"
    - button "Change language"
    - button "Toggle theme"
    - status: Backend running
    - button "Exit app"
- main:
  - complementary:
    - text: PROJECT EXPLORER
    - button "Home"
    - paragraph: Open a project to explore its data and processing history.
    - button "New project"
    - button "Downloads"
    - button "Files view" [disabled]
    - button "Data Library"
  - separator "Resize project explorer"
  - main:
    - tablist "Workflow pages":
      - tab "1 Search & download"
      - tab "2 Data & preparation" [disabled]
      - tab "3 Parameters & generation" [disabled]
      - tab "4 Run" [disabled]
      - tab "5 Products & QC" [disabled]
    - heading "Background activity" [level=1]
    - paragraph: Open the owning project to inspect processing. Downloads remain available globally.
    - button "Downloads"
    - list:
      - listitem:
        - text: Picker existing 0 processing jobs
        - button "Open project"
- contentinfo:
  - text: Local engine
  - separator
  - text: 0 processing jobs
  - button "Jobs"
  - button "Downloads"
  - text: No project open
```