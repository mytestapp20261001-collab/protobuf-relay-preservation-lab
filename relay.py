"""An old-schema bytes -> bytes relay. This process never loads v2 bindings."""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "generated" / "v1"))
import envelope_pb2 as old
from google.protobuf import json_format
from google.protobuf.message import DecodeError

MAX_BYTES = 65536
MODES = ("preserve", "json", "fields", "passthrough")


def copy_known_fields(source, target):
    """Deliberately lossy negative control, including nested reconstruction."""
    for field, value in source.ListFields():
        if field.is_repeated:
            destination = getattr(target, field.name)
            if field.message_type:
                for item in value:
                    copy_known_fields(item, destination.add())
            else:
                destination.extend(value)
        elif field.message_type:
            nested = getattr(target, field.name)
            nested.SetInParent()
            copy_known_fields(value, nested)
        else:
            setattr(target, field.name, value)


def transform(payload: bytes, mode: str = "preserve") -> bytes:
    if mode not in MODES:
        raise ValueError("unknown relay mode")
    if len(payload) > MAX_BYTES:
        raise ValueError("message exceeds 64 KiB sample limit")
    source = old.Envelope.FromString(payload)
    if mode == "passthrough":
        return payload
    if source.hops == 0xFFFFFFFF:
        raise ValueError("hop counter would overflow")
    result = old.Envelope()
    if mode == "preserve":
        result.CopyFrom(source)
    elif mode == "json":
        # Parse OLD-schema JSON: failure must be data loss, not unknown-key rejection.
        json_format.Parse(json_format.MessageToJson(source), result)
    else:
        copy_known_fields(source, result)
    result.hops += 1
    output = result.SerializeToString()
    if len(output) > MAX_BYTES:
        raise ValueError("transformed message exceeds 64 KiB sample limit")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="preserve")
    args = parser.parse_args()
    try:
        output = transform(sys.stdin.buffer.read(MAX_BYTES + 1), args.mode)
    except (ValueError, TypeError, DecodeError) as error:
        print(f"relay rejected input: {type(error).__name__}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
