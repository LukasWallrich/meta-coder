# Audit and reproducibility

Choose **Download audit ZIP** on Results, or **Download project and audit** in Project settings. The ZIP includes your current project and the persistent history of AI actions recorded by this version of MetaCoder.

## What is recorded

| Record | Included information |
| --- | --- |
| Application | App version, source fingerprint and source ZIP, installed dependency versions, Python version, and platform |
| Run | Selected PDFs, provider/model, pacing and parallelism, settings, final statuses, coded-data and evidence CSV snapshots |
| Inputs | Saved manual and coding sheet plus effective inputs passed to the action, original study PDFs or uploaded draft documents, conversion notes |
| Each request | UTC start/end timestamps, endpoint without authentication, exact request body with prompts, schema, model ID, and explicitly supplied generation settings |
| Each response | Full response envelope, original response text, provider-reported model/version, response ID, fingerprint and usage when supplied |
| Outcomes | Parsed/validated result, repaired JSON where applicable, errors, retries, and linkage from current results to the corresponding operation |
| Export | Export timestamp, project identity, current run settings, and SHA-256 checksums for every other file in the ZIP |

All roles and prompts the app sends are in the request body. Native PDF request bodies include the encoded PDF; text-based requests include the extracted text exactly as sent. Server-side prompts or processing that a provider does not return cannot be captured.

AI manual drafting and coding-sheet conversion are recorded even if you discard the generated draft. Automatic HTTP retries have separate exchange records; an explicit extraction retry creates a new operation. The working result files may be replaced, but the earlier audit records remain.

## Read the archive

Unzip the export and open `export_manifest.json`. Every entry in `files` has a checksum and byte count. Blob paths in audit records are relative to the ZIP root.

- `audit/operations/<id>/operation.json` identifies an action and references its app source, inputs, and result.
- `exchange-0001.json`, `exchange-0002.json`, and so on describe the individual HTTP attempts for that action.
- `audit/blobs/<sha256>` contains the referenced bytes. Shared inputs are stored once, so these files do not have extensions. Read the record to see whether the blob is JSON, a PDF, CSV, original uploaded document, or the application source ZIP.
- An `extraction_run` operation groups per-PDF operations through their `settings.run_id`. Its `final_results.json` input includes carried-over results from previous runs.
- Current per-PDF JSON/YAML results contain `audit_operation_id` when provenance is available.

An `in_progress` record with no finish time means the process was interrupted or the export was taken while the action was still running. It does not establish that the provider completed the request. Export after actions finish for a complete record.

## Verify an export

After unzipping, run this Python snippet from the extracted directory:

```python
import hashlib
import json
from pathlib import Path

root = Path.cwd()
manifest = json.loads((root / "export_manifest.json").read_text())
for name, expected in manifest["files"].items():
    content = (root / name).read_bytes()
    assert len(content) == expected["bytes"], name
    assert hashlib.sha256(content).hexdigest() == expected["sha256"], name
print("All exported file checksums match.")
```

Checksums detect changed bytes relative to the manifest; they are not a digital signature or independent proof of when the work was performed.

## Retention and credentials

Changing a manual or clearing generated output removes the working results but preserves `audit/`, including historical copies of inputs and outputs. Removing a source PDF also leaves any previously recorded input snapshot in the audit history. Deleting the whole project removes its audit history too. Keep exported ZIPs if you need an independent backup.

API authentication headers and keys are excluded. If a known API key is echoed in a response, it is replaced with `[REDACTED]` in the audit record. Exports still contain your research documents, prompts, conversion notes, endpoint addresses, and model output.

## Limits of reproducibility

Older runs cannot acquire missing timestamps, exact prompts, or full response envelopes retrospectively. Their surviving result files are still exported; absent audit records mean provenance is incomplete.

The selected model ID is always recorded. A provider-reported model/version or fingerprint is recorded only when supplied, otherwise it is null. A reported model name may still be an alias rather than an immutable model revision. Unspecified generation parameters use provider defaults, which are not inferred or invented in the audit log.

You can inspect and reconstruct the recorded requests, but hosted model changes, hidden server settings, PDF preprocessing, and nondeterminism can prevent byte-identical results. There is no automatic replay feature. Repeating a request requires provider access and may incur a new charge.
