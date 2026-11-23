"""Per-release resolution of scan integrity/tracklist warnings."""
import unittest

from test_audio_safety import mcc


class ReleaseAuditActions(unittest.TestCase):
    def setUp(self):
        self.snapshots = [
            {"release_id": 7, "action": "ADD", "name": "Damaged candidate", "audit_issues": ["Corrupt/unreadable 07.flac: invalid sync code"]},
            {"release_id": 8, "action": "REPLACE", "name": "Tracklist issue", "audit_issues": ["missing track number(s): 2"]},
            {"release_id": 9, "action": "KEEP", "name": "Clean release", "audit_issues": []},
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

    def test_release_map_exposes_both_actions_at_bottom_of_details(self):
        html = mcc._webview_release_map_html()
        self.assertIn('id="auditApproveBtn"', html)
        self.assertIn('id="auditIgnoreBtn"', html)
        self.assertIn('> Keep</button>', html)
        self.assertIn('> Skip</button>', html)
        self.assertIn('bridge.reviewRelease(Number(n.id),"approve"', html)
        self.assertIn('bridge.reviewRelease(Number(n.id),"ignore"', html)
        self.assertIn("""+'<div id="tracks">'+tracks+'</div>'+auditActions;""", html)


if __name__ == "__main__":
    unittest.main()
