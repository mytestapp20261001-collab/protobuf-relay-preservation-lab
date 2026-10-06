"""Rebuild original synthetic fixtures and explicit, reviewable input expectations."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "generated" / "v2"))
import envelope_pb2 as new

EMPTY = {
    "id": "", "hops": 0, "state": 0, "samples": [],
    "priority.value": 0, "priority.present": False,
    "details.present": False, "details.name": "",
    "details.retry_after.value": 0, "details.retry_after.present": False,
    "details.tags": [], "details.future_note": "",
    "details.future_zero.value": 0, "details.future_zero.present": False,
    "details.future_chunks": [], "future_label": "",
    "future_zero.value": 0, "future_zero.present": False, "future_routes": [],
}


def cases():
    # Expectations are literals, not produced by the consumer projection.
    yield "absent", new.Envelope(id="absent"), dict(EMPTY, id="absent")
    m = new.Envelope(id="known-defaults", priority=0)
    m.details.retry_after = 0
    yield "known-defaults", m, EMPTY | {
        "id": "known-defaults", "priority.present": True,
        "details.present": True, "details.retry_after.present": True,
    }
    m = new.Envelope(id="future-top", hops=2, future_label="retain me",
                     future_zero=0, future_routes=["east", "west", "east"])
    yield "future-top", m, EMPTY | {
        "id": "future-top", "hops": 2, "future_label": "retain me",
        "future_zero.present": True, "future_routes": ["east", "west", "east"],
    }
    m = new.Envelope(id="future-nested", hops=4)
    m.details.name = "known child"
    m.details.future_note = "inside known child"
    m.details.future_zero = 0
    m.details.future_chunks.extend([b"\x00\xff", b"", b"abc"])
    yield "future-nested", m, EMPTY | {
        "id": "future-nested", "hops": 4, "details.present": True,
        "details.name": "known child", "details.future_note": "inside known child",
        "details.future_zero.present": True, "details.future_chunks": ["00ff", "", "616263"],
    }
    m = new.Envelope(id="mixed", hops=9, priority=0, state=new.DEFERRED,
                     samples=[7, -2, 7, 0], future_label="new", future_zero=0,
                     future_routes=["one", "two"])
    m.details.name = "nested"
    m.details.retry_after = 0
    m.details.tags.extend(["b", "a", "b"])
    m.details.future_note = "child extension"
    m.details.future_zero = 0
    m.details.future_chunks.extend([b"a", b"b"])
    yield "mixed", m, EMPTY | {
        "id": "mixed", "hops": 9, "state": 2, "samples": [7, -2, 7, 0],
        "priority.present": True, "details.present": True, "details.name": "nested",
        "details.retry_after.present": True, "details.tags": ["b", "a", "b"],
        "details.future_note": "child extension", "details.future_zero.present": True,
        "details.future_chunks": ["61", "62"], "future_label": "new",
        "future_zero.present": True, "future_routes": ["one", "two"],
    }


def main():
    folder = ROOT / "fixtures"
    folder.mkdir(exist_ok=True)
    manifest = []
    for name, message, expected in cases():
        (folder / f"{name}.bin").write_bytes(message.SerializeToString(deterministic=True))
        manifest.append({"name": name, "input": expected})
    (folder / "expected.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
