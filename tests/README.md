# Repository-Level Tests

Cross-service and stack-wide checks live here.

## Layout
- `tests/system/`: end-to-end tests across multiple services.
- `tests/smoke-stack/`: full-stack smoke scripts.
- `tests/fixtures-shared/`: reusable fixtures for multiple services.
- `tests/scripts/`: helper runners/utilities.

## Notes
- Service-local tests must remain inside each service under:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/contract/`
  - `tests/smoke/`
  - `tests/sandbox/`
