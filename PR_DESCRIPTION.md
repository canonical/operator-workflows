## Summary
Temporarily disable Trivy scans in integration workflows due to the ongoing `aquasecurity/trivy-action` security incident.

## What changed
- Disabled the Trivy FS scan step in `.github/workflows/integration_test_run.yaml`
- Disabled the Trivy image scan step in `.github/workflows/integration_test.yaml`
- Added clear inline messaging so this is easy to revert once upstream is trusted again

## Why
`trivy-action` is currently reported as compromised. This change is an immediate containment measure to prevent execution of untrusted action code in CI.

## Follow-up
Re-enable scanning only after moving to a verified safe alternative (prefer pinned commit SHA, not a tag) and rotating any potentially exposed credentials.
