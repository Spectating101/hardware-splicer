# Engineering review

Hardware Splicer can attach deterministic external design-review evidence to an existing build without giving an external tool authority over the project.

The first supported adapter is [kicad-happy](https://github.com/aklofas/kicad-happy). It is used as a read-only local sidecar for schematic, PCB, and Gerber analysis.

## Operator value

From the **Design** stage:

1. Inspect the KiCad board and schematic.
2. Confirm KiCad compile truth and DRC status.
3. Run **Engineering review**.
4. Review blockers, warnings, affected components/nets, confidence, and recommendations.
5. Download or package `build_compilation/ENGINEERING_REVIEW.json` with the rest of the project.

The review may inform or block a release policy. It never grants fabrication, flashing, or power-on authorization.

## Configure kicad-happy

Clone the upstream project outside Hardware Splicer and point the product API at it:

```bash
git clone https://github.com/aklofas/kicad-happy.git ~/tools/kicad-happy
export HARDWARE_SPLICER_KICAD_HAPPY_ROOT=~/tools/kicad-happy
```

Restart `hs-serve` or `make splice-ui-serve` after changing the environment.

No upstream code is vendored into Hardware Splicer. The adapter records the local Git revision when available.

## API

### Capability and latest result

```http
POST /v1/build-files/engineering-review/status
Content-Type: application/json

{"build_dir":"/tmp/hardware_splicer_api/example"}
```

The response reports:

- whether the adapter is available;
- which schematic, PCB, or Gerber inputs were found;
- which analyses can run;
- the latest normalized review, when present.

### Run review

```http
POST /v1/build-files/engineering-review/run
Content-Type: application/json

{
  "build_dir":"/tmp/hardware_splicer_api/example",
  "timeout_s":180,
  "force":false
}
```

Unchanged inputs and adapter revision reuse the existing result unless `force=true`.

## Evidence and safety contract

Every run records:

- adapter ID, local root, and Git revision when available;
- source paths and SHA-256 hashes;
- command, exit code, duration, timeout state, bounded stdout, and bounded stderr;
- analyzer type and upstream schema version;
- normalized findings and assessments;
- authority ceiling of `observed`;
- raw analyzer JSON artifacts;
- a failure casefile when an analyzer fails.

Provider credentials and unrelated application environment variables are removed before analyzer launch. The adapter uses a dedicated process group and terminates it on timeout.

Input artifacts are hashed again after execution. Any mutation causes the review to fail closed and discards normalized findings from that run.

This is a bounded local-process integration, not a complete hostile-code sandbox. Run untrusted analyzer checkouts in a network-disabled, filesystem-restricted container.

## Result interpretation

| Product status | Meaning |
|---|---|
| `blocked` | At least one external finding maps to a blocker severity. |
| `review_required` | No blocker, but one or more warnings require disposition. |
| `partial` | Some analyzers succeeded and others failed. |
| `failed` | No trusted analyzer output was produced. |
| `clear` | No external blocker or warning was reported. |

A `clear` external review does **not** mean fabrication-ready. KiCad ERC/DRC, project gates, bench evidence, and human authorization remain independent requirements.
