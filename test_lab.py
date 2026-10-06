import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import lab
import make_fixtures

ROOT = Path(__file__).resolve().parent
TOP = {"future_label", "future_zero.present", "future_routes"}
NESTED = {"details.future_note", "details.future_zero.present", "details.future_chunks"}
LOSSES = {"absent": set(), "known-defaults": set(), "future-top": TOP,
          "future-nested": NESTED, "mixed": TOP | NESTED}


def cli(name, *args, payload=None):
    return subprocess.run([sys.executable, str(ROOT / name), *args], input=payload,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)


class ContractTests(unittest.TestCase):
    def test_preserving_relay(self):
        result = lab.check("preserve")
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["cases"]), 5)

    def test_json_exact_losses(self):
        self.check_loss_control("json")

    def test_recursive_copy_exact_losses(self):
        self.check_loss_control("fields")

    def check_loss_control(self, mode):
        result = lab.check(mode)
        self.assertFalse(result["passed"])
        for case in result["cases"]:
            self.assertEqual(set(case["differences"]), LOSSES[case["case"]])

    def test_passthrough_rejected_only_for_missing_edit(self):
        result = lab.check("passthrough")
        self.assertFalse(result["passed"])
        for case in result["cases"]:
            self.assertEqual(set(case["differences"]), {"hops"})

    def test_literal_fixture_expectations(self):
        manifest = json.loads((ROOT / "fixtures/expected.json").read_text())
        for (name, message, literal), saved in zip(make_fixtures.cases(), manifest, strict=True):
            self.assertEqual(saved, {"name": name, "input": literal})
            self.assertEqual(lab.view(message), literal)
            payload = (ROOT / "fixtures" / f"{name}.bin").read_bytes()
            self.assertEqual(lab.view(lab.new.Envelope.FromString(payload)), literal)
            self.assertEqual(payload, message.SerializeToString(deterministic=True))

    def test_absent_vs_present_default(self):
        a = lab.new.Envelope()
        b = lab.new.Envelope(priority=0)
        self.assertEqual(a.priority, b.priority)
        self.assertEqual(set(lab.differences(lab.view(a), lab.view(b))), {"priority.present"})

    def test_empty_nested_presence(self):
        a = lab.new.Envelope()
        b = lab.new.Envelope()
        b.details.SetInParent()
        self.assertEqual(set(lab.differences(lab.view(a), lab.view(b))), {"details.present"})
        for mode in ("preserve", "json", "fields"):
            result = lab.new.Envelope.FromString(lab.call_relay(b.SerializeToString(), mode))
            self.assertTrue(result.HasField("details"))

    def test_actual_v1_binding(self):
        code = "import relay; d=relay.old.Envelope.DESCRIPTOR; print(d.full_name); print(','.join(d.fields_by_name)); print(','.join(relay.old.Details.DESCRIPTOR.fields_by_name))"
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, check=True)
        self.assertEqual(r.stdout.decode().splitlines(), [
            "relay_lab.Envelope", "id,hops,details,priority,state,samples", "name,retry_after,tags"])
        self.assertEqual(lab.new.Envelope.DESCRIPTOR.full_name, "relay_lab.Envelope")

    def test_deterministic_semantic_variants(self):
        rng = random.Random(3401)
        for i in range(20):
            m = lab.new.Envelope(id=f"variant-{i}", hops=rng.randrange(1000),
                                 state=rng.choice([0, 1, 2, 19]), future_label=f"new-{i}",
                                 future_routes=["r", str(i), "r"], samples=[i, -i, 0])
            if i % 2:
                m.priority = 0
                m.future_zero = 0
            m.details.name = "known"
            m.details.future_note = str(i)
            m.details.future_chunks.extend([bytes([i]), b"", bytes([i])])
            if i % 3:
                m.details.retry_after = 0
                m.details.future_zero = 0
            payload = m.SerializeToString()
            expected = lab.new.Envelope()
            expected.CopyFrom(m)
            expected.hops += 1
            result = lab.new.Envelope.FromString(lab.call_relay(payload, "preserve"))
            self.assertEqual(result, expected)
            self.assertEqual(m.hops + 1, result.hops)

    def test_known_defaults_survive_negative_controls(self):
        payload = (ROOT / "fixtures/mixed.bin").read_bytes()
        for mode in ("json", "fields"):
            m = lab.new.Envelope.FromString(lab.call_relay(payload, mode))
            self.assertTrue(m.HasField("priority"))
            self.assertTrue(m.details.HasField("retry_after"))
            self.assertEqual(m.state, 2)  # An unknown proto3 enum number need not be lost.
            self.assertEqual(list(m.samples), [7, -2, 7, 0])
            self.assertEqual(list(m.details.tags), ["b", "a", "b"])

    def test_cli_exit_codes(self):
        for mode, expected in (("preserve", 0), ("json", 1), ("fields", 1), ("passthrough", 1)):
            result = cli("lab.py", "--mode", mode)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertEqual(json.loads(result.stdout)["mode"], mode)

    def test_malformed_input(self):
        result = cli("relay.py", payload=b"\x80")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(b"Traceback", result.stderr)

    def test_oversized_input(self):
        result = cli("relay.py", payload=b"x" * (lab.MAX_BYTES + 1))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")

    def test_overflow_rejected(self):
        result = cli("relay.py", payload=lab.new.Envelope(hops=2**32-1).SerializeToString())
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")

    def test_empty_protobuf_is_valid(self):
        r = cli("relay.py", payload=b"")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(lab.new.Envelope.FromString(r.stdout).hops, 1)

    def test_output_boundary(self):
        # A 64 KiB input is legal; adding hops=1 makes this output too large.
        m = lab.new.Envelope(future_label="x" * (lab.MAX_BYTES - 4))
        payload = m.SerializeToString()
        self.assertEqual(len(payload), lab.MAX_BYTES)
        self.assertEqual(cli("relay.py", payload=payload).returncode, 2)

    def test_invalid_mode(self):
        self.assertEqual(cli("relay.py", "--mode", "no", payload=b"").returncode, 2)
        with self.assertRaises(ValueError):
            lab.check("no")

    def test_checker_rejects_failed_relay(self):
        fake = subprocess.CompletedProcess([], 2, b"", b"rejected")
        with patch.object(lab.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "exited 2"):
                lab.call_relay(b"", "preserve")

    def test_checker_timeout_is_not_semantic_failure(self):
        with patch.object(lab.subprocess, "run", side_effect=subprocess.TimeoutExpired("sample", 5)):
            with self.assertRaises(subprocess.TimeoutExpired):
                lab.call_relay(b"", "preserve")

    def test_checker_rejects_oversized_output(self):
        fake = subprocess.CompletedProcess([], 0, b"x" * (lab.MAX_BYTES + 1), b"")
        with patch.object(lab.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "output exceeds"):
                lab.call_relay(b"", "preserve")

    def test_fixture_manifest_disagreement(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "fixtures"
            target.mkdir()
            target.joinpath("absent.bin").write_bytes(b"")
            target.joinpath("expected.json").write_text(json.dumps([
                {"name": "absent", "input": {"id": "wrong"}}]))
            with patch.object(lab, "ROOT", Path(folder)):
                with self.assertRaisesRegex(ValueError, "disagreement"):
                    lab.check("preserve")


if __name__ == "__main__":
    unittest.main()
