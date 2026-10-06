"""Check one concrete old-schema relay contract using synthetic binary fixtures."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "generated" / "v2"))
import envelope_pb2 as new
from google.protobuf.message import DecodeError

MAX_BYTES = 65536
MODES = ("preserve", "json", "fields", "passthrough")


def view(message):
    """Explicit semantic contract. Presence is separate from accessor defaults."""
    d = message.details
    return {
        "id": message.id, "hops": message.hops, "state": message.state,
        "samples": list(message.samples),
        "priority.value": message.priority, "priority.present": message.HasField("priority"),
        "details.present": message.HasField("details"), "details.name": d.name,
        "details.retry_after.value": d.retry_after,
        "details.retry_after.present": d.HasField("retry_after"),
        "details.tags": list(d.tags), "details.future_note": d.future_note,
        "details.future_zero.value": d.future_zero,
        "details.future_zero.present": d.HasField("future_zero"),
        "details.future_chunks": [v.hex() for v in d.future_chunks],
        "future_label": message.future_label,
        "future_zero.value": message.future_zero,
        "future_zero.present": message.HasField("future_zero"),
        "future_routes": list(message.future_routes),
    }


def differences(expected, actual):
    return {key: {"expected": expected.get(key), "actual": actual.get(key)}
            for key in sorted(set(expected) | set(actual)) if expected.get(key) != actual.get(key)}


def call_relay(payload, mode):
    # A fixed local sample, not an arbitrary-command service or a code sandbox.
    result = subprocess.run(
        [sys.executable, str(ROOT / "relay.py"), "--mode", mode],
        input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT, timeout=5, check=False,
    )
    if result.returncode:
        raise ValueError(f"relay exited {result.returncode}")
    if len(result.stdout) > MAX_BYTES:
        raise ValueError("relay output exceeds the sample limit")
    return result.stdout


def check(mode):
    if mode not in MODES:
        raise ValueError("unknown relay mode")
    manifest = json.loads((ROOT / "fixtures" / "expected.json").read_text())
    reports = []
    for case in manifest:
        payload = (ROOT / "fixtures" / f"{case['name']}.bin").read_bytes()
        if len(payload) > MAX_BYTES:
            raise ValueError("fixture exceeds sample limit")
        before = view(new.Envelope.FromString(payload))
        if before != case["input"]:
            raise ValueError(f"fixture/manifest disagreement: {case['name']}")
        expected = dict(case["input"], hops=case["input"]["hops"] + 1)
        output = call_relay(payload, mode)
        actual = view(new.Envelope.FromString(output))
        diff = differences(expected, actual)
        reports.append({"case": case["name"], "passed": not diff, "differences": diff})
    return {"mode": mode, "passed": all(r["passed"] for r in reports), "cases": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="preserve")
    args = parser.parse_args()
    try:
        report = check(args.mode)
    except (ValueError, OSError, DecodeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
