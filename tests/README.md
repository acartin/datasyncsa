# Repository-Level Tests

Cross-service and stack-wide checks live here.

## Layout
- `tests/system/`: end-to-end tests across multiple services.
- `tests/smoke-stack/`: full-stack smoke scripts.
- `tests/sandbox/realtor/`: manual simulators/benchmarks for realtor v2.
- `tests/sandbox/dentist/`: manual simulators/benchmarks for dentist v2.
- `tests/sandbox/*.py`: legacy wrappers kept for backward compatibility.
- `tests/fixtures-shared/`: reusable fixtures for multiple services.
- `tests/scripts/`: helper runners/utilities.

## Notes
- Service-local tests must remain inside each service.
- Root-level tests are only for cross-service/system/sandbox use cases.
