"""Per-release resolution of scan integrity/tracklist warnings."""
import unittest

from test_audio_safety import mcc


class ReleaseAuditActions(unittest.TestCase):
    def setUp(self):
        self.snapshots = [
            {"release_id": 7, "action": "KEEP", "name": "Damaged candidate", "audit_issues": ["Corrupt/unreadable 07.flac: invalid sync code"]},
            {"release_id": 8, "action": "ADD", "name": "Tracklist issue", "audit_issues": ["missing track number(s): 2"]},
            {"release_id": 9, "action": "SKIP", "name": "Clean release", "audit_issues": []},
        ]
        self.blocked = set()
        self.pinned = set()

    def test_unreviewed_audits_remain_export_blockers(self):
        pending = mcc._unreviewed_release_audit_blockers(self.snapshots, self.blocked, self.pinned)
        self.assertEqual([row["release_id"] for row in pending], [7, 8])

    def test_approve_pins_release_and_resolves_only_its_blocker(self):
        changed = mcc._apply_release_audit_decision(7, "approve", self.blocked, self.pinned)
        self.assertTrue(changed)
        self.assertEqual(self.pinned, {7})
        self.assertEqual(self.blocked, set())
        pending = mcc._unreviewed_release_audit_blockers(self.snapshots, self.blocked, self.pinned)
        self.assertEqual([row["release_id"] for row in pending], [8])
        self.assertEqual(self.snapshots[0]["audit_issues"], ["Corrupt/unreadable 07.flac: invalid sync code"])

    def test_ignore_excludes_release_and_resolves_only_its_blocker(self):
        changed = mcc._apply_release_audit_decision(7, "ignore", self.blocked, self.pinned)
        self.assertTrue(changed)
        self.assertEqual(self.blocked, {7})
        self.assertEqual(self.pinned, set())
        pending = mcc._unreviewed_release_audit_blockers(self.snapshots, self.blocked, self.pinned)
        self.assertEqual([row["release_id"] for row in pending], [8])

    def test_approve_and_ignore_are_mutually_exclusive_and_reversible(self):
        mcc._apply_release_audit_decision(7, "approve", self.blocked, self.pinned)
        mcc._apply_release_audit_decision(7, "ignore", self.blocked, self.pinned)
        self.assertEqual(self.blocked, {7})
        self.assertEqual(self.pinned, set())
        mcc._apply_release_audit_decision(7, "approve", self.blocked, self.pinned)
        self.assertEqual(self.blocked, set())
        self.assertEqual(self.pinned, {7})

    def test_invalid_decision_is_rejected_without_mutation(self):
        with self.assertRaises(ValueError):
            mcc._apply_release_audit_decision(7, "skip", self.blocked, self.pinned)
        self.assertEqual(self.blocked, set())
        self.assertEqual(self.pinned, set())

    def test_release_map_exposes_one_choice_group(self):
        html = mcc._webview_release_map_html()
        self.assertIn('id="releaseChoice"', html)
        self.assertIn('["Auto","Keep","Skip"]', html)
        self.assertIn('bridge.setReleaseChoice(Number(n.id)', html)
        self.assertNotIn('id="auditActions"', html)


if __name__ == "__main__":
    unittest.main()
