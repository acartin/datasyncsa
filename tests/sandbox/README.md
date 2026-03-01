# Sandbox Tests

Manual and exploratory scripts that hit running services.

## Structure
- `tests/sandbox/realtor/`: realtor-focused simulators and latency checks.
- `tests/sandbox/dentist/`: dentist-focused simulators.
- `tests/sandbox/*.py`: legacy wrappers for older command paths.

## Execution
- Realtor single conversation:
  - `python3 tests/sandbox/realtor/simulate_chat_realtor.py --auto`
- Realtor multi-scenario:
  - `python3 tests/sandbox/realtor/simulate_multichat_realtor.py --all`
- Realtor Gemini benchmark:
  - `RUN_GEMINI_BENCH=1 python3 -m pytest -q tests/sandbox/realtor/test_gemini_latency_realtor_contract.py -s`
- Dentist simulator:
  - `python3 tests/sandbox/dentist/simulate_chat_dentist.py --auto`

These scripts are not blocking CI unless explicitly added to a CI job.
