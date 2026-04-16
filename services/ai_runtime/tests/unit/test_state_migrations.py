import unittest

from services.ai_runtime.domain.state import CURRENT_SCHEMA_VERSION
from services.ai_runtime.runtime.state_migrations import apply_migrations


class StateMigrationsTests(unittest.TestCase):
    def test_apply_migrations_adds_schema_version_to_v0_payload(self) -> None:
        payload = {"client_id": "test", "vertical": "realtor"}

        result = apply_migrations(payload)

        self.assertEqual(result["schema_version"], CURRENT_SCHEMA_VERSION)

    def test_apply_migrations_is_idempotent_at_current_version(self) -> None:
        payload = {"schema_version": CURRENT_SCHEMA_VERSION, "client_id": "test"}

        result = apply_migrations(payload)

        self.assertEqual(result["schema_version"], CURRENT_SCHEMA_VERSION)

    def test_apply_migrations_preserves_other_fields(self) -> None:
        payload = {"client_id": "abc", "messages": [{"role": "user", "content": "hi"}]}

        result = apply_migrations(payload)

        self.assertEqual(result["client_id"], "abc")
        self.assertEqual(result["messages"], [{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
