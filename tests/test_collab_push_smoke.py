import unittest


class TestCollaboratorPushSmoke(unittest.TestCase):
    def test_branch_push_smoke(self) -> None:
        self.assertEqual("simon".upper(), "SIMON")
