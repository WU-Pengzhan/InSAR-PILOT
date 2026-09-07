# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: reconnect.spec.ts >> reopens the same browser profile after the browser process exits
- Location: ..\..\..\..\..\..\wsl$\Ubuntu\Ubuntu\home\griffin\projects\insar-pilot\frontend\e2e\reconnect.spec.ts:3:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'Recent projects', exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: 'Recent projects', exact: true }) with timeout 5000ms
  - waiting for getByRole('heading', { name: 'Recent projects', exact: true })

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
- main:
  - heading "Connect this browser" [level=1]
  - paragraph: This browser has no valid local session. Open the workbench with the launcher on the computer running the service.
  - code: insar-pilot-web --browser firefox
  - paragraph: For WSL, run the command in Ubuntu; choose firefox, chrome, edge or default to open that Windows browser. Use the same --state directory if you started the service with a custom one.
  - paragraph: This browser keeps its connection for 30 days, including app restarts. A new browser, private window or cleared cookies requires connecting again.
  - button "Check connection again"
- contentinfo:
  - text: Local engine
  - separator
  - text: 0 processing jobs
  - button "Jobs"
  - button "Downloads"
  - text: No project open
```