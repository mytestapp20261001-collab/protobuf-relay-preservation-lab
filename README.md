# Protobuf relay preservation lab

**An older relay can accept a newer message and silently drop data while copying it.** This small executable example checks the actual application transformation:

`v2 producer → v1 relay increments hops → v2 consumer`

The safe relay copies the whole old-schema message. Two deliberately lossy relays use JSON and recursive field-by-field reconstruction. A fourth relay passes the original bytes through; the checker rejects it because the required edit never happened.

## Run the contract

Tested target: Linux x86_64, Python **3.12.14**, protobuf **7.36.2**. Start in this repository's root. The commands install into an isolated environment; the lab itself never installs packages or accesses the network.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -B lab.py --mode preserve     # exit 0: all five cases pass
.venv/bin/python -B lab.py --mode json         # exit 1: specified new fields lost
.venv/bin/python -B lab.py --mode fields       # exit 1: specified new fields lost
.venv/bin/python -B lab.py --mode passthrough  # exit 1: required hops edit missing
.venv/bin/python -B -m unittest -v
```

`lab.py` prints JSON with each differing semantic field, its expected value and its actual value. Exit **0** means every case passed, **1** means the contract failed, and **2** means a setup/input/execution error. Negative-control commands intentionally return 1. A crash or parse error is not accepted as proof of the intended data-loss behavior.

Generated Python bindings and the five original synthetic binary inputs are checked in. They are produced by the pinned compiler, not a hand-written wire encoder. No gRPC server, broker, network socket, schema registry or external data is used. The compiler is only needed to regenerate them:

```sh
.venv/bin/python -m pip install --only-binary=:all: -r requirements-dev.txt
.venv/bin/python -B generate.py
.venv/bin/python -B make_fixtures.py
git diff --exit-code
.venv/bin/python -B -m unittest -v
```

The fixed development set uses grpcio-tools 1.84.0, which reports libprotoc 35.1 and emits Python gencode 7.35.1, with runtime 7.36.2. These are different components' version numbers. CI regenerates both schemas and fixtures and requires an unchanged tracked tree. This is one supported combination, not a runtime-version compatibility matrix.

## What the five cases prove

- `absent`: optional fields and the child message remain absent
- `known-defaults`: explicitly present zero values stay present through an old schema that also uses `optional`
- `future-top`: new top-level text, explicit zero presence and repeated routes survive
- `future-nested`: new fields inside a child message already known to v1 survive, including repeated byte values and their order
- `mixed`: combines extensions, known repeated values, explicit defaults and a new proto3 enum number

For JSON and field-copy controls, `absent` and `known-defaults` pass. The other cases fail for exact new-field differences. The new enum number still survives these controls; unknown enum numbers are not equivalent to unknown fields. Every control must still increment `hops` except the deliberately unchanged passthrough.

`fixtures/expected.json` records explicit input semantics. The expected output is those same semantics with `hops + 1`. Expected presence flags are independent of accessor default values. The checker compares values, presence, repeated order and the requested edit, rather than serialized byte identity. Valid Protobuf reserialization need not preserve byte order.

Both schemas use the same `relay_lab.Envelope` name. The producer/consumer process loads v2 bindings; the separate relay process loads only v1. “v1” and “v2” mean revisions of the application's schema, not different or obsolete Protobuf runtimes.

## Adapt it to your relay

1. Read `relay.py:transform`. Its contract is `bytes → bytes`; the sample must increment only `hops` once while retaining all other declared semantics
2. Replace the `preserve` branch with the actual trusted application transformation you want to test. Keep the known-field edit assertion so an accidental bypass cannot pass
3. For a different message, substitute its old/new schemas, generate both separately, and update the synthetic fixtures and explicit `lab.py:view` projection. Review the expected presence semantics and allowed edits with that application's contract
4. Keep a passing whole-message-copy control and the two actual lossy transformations. Run the complete test suite before trusting a changed checker

This is a small, editable example for a specific preservation policy. It does not automatically inspect an arbitrary project or prove every unknown field is safe to forward. Gateways that intentionally filter fields need different expectations. Never insert production payloads, secrets or personal data into this public fixture repository.

Presence needs special care: if the newer schema makes a known scalar `optional` while the old schema leaves it implicit, even correct binary decode/re-encode can lose present-default information. Whole-message copying cannot recover presence already discarded by the old schema. Here known tracked scalars are `optional` in both revisions.

## Limits and maintenance

The sample reads at most 64 KiB plus one byte, rejects oversized/malformed input and hop overflow, and checks output size. Its fixed child process has a five-second timeout. It captures that trusted sample's output before checking its size; this is not a sandbox or a resource-safety guarantee for replacement code. An adapted relay that spawns descendants, emits unbounded output or performs network/file actions is outside this harness's protection. Run only code you trust.

The lab does not prove cross-language behavior, proto2 closed-enum behavior, oneof evolution, maps, duplicate-tag semantics, runtime security or a production deployment's compatibility. Linux/Python 3.12.14 is the verified execution target. It performs no telemetry, uploads or real-system modifications. Active expansion stops at this bounded example; reproducible defects, relevant dependency security changes or concrete integration needs can justify a maintenance update.

### Existing tools and technical sources

- [Protobuf unknown-field guidance](https://protobuf.dev/programming-guides/proto3/#unknown-fields) documents JSON/field-copy losses and whole-message copying
- [Protobuf field presence](https://protobuf.dev/programming-guides/field_presence/) explains absent versus present-default behavior
- [Protobuf runtime compatibility](https://protobuf.dev/support/cross-version-runtime-guarantee/) defines supported generated-code/runtime combinations
- [Buf breaking](https://buf.build/docs/breaking/) compares schema revisions; [Protobuf conformance tests](https://github.com/protocolbuffers/protobuf/blob/main/conformance/README.md) test runtime implementations

Use those established tools for their purposes. This lab adds a small application-transform acceptance example with genuine passing and failing controls. It makes no claim of novelty, independent usage, demand or universal compatibility.

## Optional creator invitation

This utility is made by the creator of [MyTest](https://mytest.app). For a separate private game, [Code puzzle](https://mytest.app/code-puzzle) gives you six guesses to find a fixed three-digit answer using the clues from earlier guesses. You can reveal the answer and stop at any time. The answer and guesses remain in page memory and disappear on reload or departure; the answer is inspectable in browser tools, so this is not a secure competition.

This is an optional promotional invitation. Skip it freely. Visiting, playing or giving feedback is never required for the engineering task, and no productivity benefit is claimed.
