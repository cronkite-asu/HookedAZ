# HookedAZ guarded operations

Use this adapter for the approved static archive repair release. It targets only `hookedaz.cronkitenewsonline.com` and backs up to `datasync-efs-shared-1.jmc.asu.edu`; distribution alias and root origin are checked before writes. No configuration/permission operations are implemented.

The current baseline was downloaded read-only using `aws s3 sync s3://hookedaz.cronkitenewsonline.com/ hookedaz-review/live-s3/ --profile csjh --only-show-errors` (no delete flag), and all 527 public object responses matched its bytes. `public-baseline.json` records those hashes.

The commands below refer to the maintenance workspace. In a fresh repository clone, run `preservation/operations/manage.py` instead and explicitly supply the external baseline, state, proof, build, validation and review paths. No operational receipt or credential is committed. Run with the AWS CLI Python. Commands below have explicit private state and baseline paths. `backup` writes only the requested backup bucket; `deploy` is reserved for root after independent review of the final built payload.

```sh
python3 -m unittest discover -s hookedaz-review/operations/tests -v
/opt/homebrew/opt/awscli/libexec/bin/python hookedaz-review/operations/manage.py baseline --state hookedaz-review/operations-state --baseline hookedaz-review/live-s3
/opt/homebrew/opt/awscli/libexec/bin/python hookedaz-review/operations/manage.py backup --state hookedaz-review/operations-state --baseline hookedaz-review/live-s3 --public-proof hookedaz-review/operations/public-baseline.json
```

The backup pins source versions, content, headers, custom metadata and tags and verifies destination versions before writing the completion receipt. Existing backup state is never overwritten; use a fresh private state directory after a failed attempt. The unique remote prefix is `hookedaz.cronkitenewsonline.com/<UTC>-before-repairs-<nonce>/`.

After final build validation and independent review, prepare/freeze the exact reviewed payload with `plan --build PATH --validation PATH --review PATH --state STATE`. `prepare` is an alias. The reviewer must include these exact lines with actual hashes:

```text
## Assessment: APPROVED
Validation SHA-256: <SHA-256 of raw validation JSON bytes>
Build manifest SHA-256: <SHA-256 of canonical sorted compact JSON build_sha256 map>
```

The canonical map digest is `manifest_digest(hashes)` in `manage.py`: UTF-8 `json.dumps(hashes, sort_keys=True, separators=(',', ':'), ensure_ascii=True)`.

Then root runs `preflight`, `deploy`, `verify`, `wait`, and `public` with the same `--state`. `upload` aliases `deploy`. Preflight checks all baseline keys/current versions/hashes/headers/tags and pinned remote backup content/metadata/tags; deployment uses conditional writes for the frozen exact changed/new keys. Assets precede HTML and the homepage. Original objects are retained. Modified existing content headers are preserved; additions have explicit MIME types.

`wait` performs one current CloudFront invalidation-status check; root polls until Completed. Invalidation includes changed object paths and their directory aliases only. If invalidation fails after source writes, the append-only journal still permits `verify` and recovery; do not claim public completion until cache verification passes.

`restore --state STATE` conditionally restores original changed existing objects and their metadata/tags without deleting versions. Added files remain unreferenced. Completed restore is terminal, and deploy refuses a restored state. Source drift, unjournaled changes, missing/modified receipts, altered build/validation/review or failed remote backup verification halt operations.

`_release_guard.py` derives from the previously reviewed Nicaragua release core; target constants/default allowlists were adapted for HookedAZ and its CLI removed. It is an internal module; run only `manage.py`. The subclass replaces generic rollback with zero-delete restore and preserves original headers. Private state, credentials, receipts and complete baseline are not public website payloads.
