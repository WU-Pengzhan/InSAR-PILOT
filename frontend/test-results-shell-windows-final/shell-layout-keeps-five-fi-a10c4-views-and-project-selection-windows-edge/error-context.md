# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: shell-layout.spec.ts >> keeps five fixed pages across auxiliary views and project selection
- Location: ..\..\..\..\..\..\wsl$\Ubuntu\Ubuntu\home\griffin\projects\insar-pilot\frontend\e2e\shell-layout.spec.ts:15:1

# Error details

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator:  getByTestId('primary-pages').getByRole('tab', { name: '3 Parameters & generation', exact: true })
Expected: "true"
Received: "false"
Timeout:  5000ms

Call log:
  - Expect "toHaveAttribute" getByTestId('primary-pages').getByRole('tab', { name: '3 Parameters & generation', exact: true }) with timeout 5000ms
  - waiting for getByTestId('primary-pages').getByRole('tab', { name: '3 Parameters & generation', exact: true })
    14 × locator resolved to <div role="tab" tabindex="-1" aria-selected="false" class="q-tab relative-position self-stretch flex flex-center text-center q-tab--inactive q-tab--no-caps q-focusable q-hoverable cursor-pointer">…</div>
       - unexpected value "false"

```

```yaml
- tab "3 Parameters & generation"
```