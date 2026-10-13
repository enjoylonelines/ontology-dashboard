# SolutionLink live failure-boundary E2E — 2026-10-13

## Purpose

This test validates the refactored Decision Workspace in a real Chromium browser
after demo-account login. It does not use the old static capture page as the
application under test.

The seeded test backend supplies login and bootstrap data. Playwright then
intercepts only the selected Case's detail and briefing responses to inject a
controlled failure packet. No production or shared database is read or written.

## Injected state and expected user-facing result

| Injected condition | Expected visible result |
| --- | --- |
| `data_status.is_stale=true` | New action candidates are withheld. |
| Missing maintenance and production context | The LLM panel lists the two missing evidence categories. |
| Summary validation failure | Generated prose is absent; the user sees why it was withheld. |
| Work order says `approved`, but no approval/assignment activity exists | The action history says `승인 이력 확인 필요`, not `점검 시작 대기`. |

## Reproduce

```bash
cd systems/frontend
npm run test:e2e:solutionlink
```

`e2e/solutionlink-live-failure-boundary.spec.ts` is the live application
boundary. The other three SolutionLink tests remain controlled component
fixtures for focused presentation states.

## Claim boundary

This is browser-level engineering acceptance evidence: real login, routing,
React rendering, state adaptation, and user-visible safety behavior were
exercised together. The injected responses are deliberately synthetic. The
result does not measure LLM accuracy, backend provider availability, real
factory data quality, user comprehension, or maintenance outcomes.
