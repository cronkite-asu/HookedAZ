# HookedAZ operations safety review

Scope: independent review of the backup/release adapter against `hookedaz-review/.pipeline/design-doc.md` and `operations/.pipeline/impl-report.md`. This assessment permits the **backup operation**. It does not approve any site payload or production upload; that requires the separate exact-build site review and guarded prepare/preflight.

## Spec Compliance

- PASS: targets are the HookedAZ bucket root, user-specified backup bucket, and verified distribution (`manage.py:26`, `:53`). The backup checks alias and the sole root website origin before mutation.
- PASS: backup requires source/destination versioning, exact local/current inventory and public baseline hashes, pins every source version/ETag/SHA/header/metadata/tag set, copies by pinned version, verifies pinned destination bytes/settings, and checks source current versions/inventory again (`manage.py:72–117`). Every backup mutation targets the destination bucket. Failed/incomplete attempts have no completion receipt and cannot silently overwrite the state.
- PASS: prepare binds review approval to raw validation and canonical complete build hashes; preserves every original key; freezes payload/evidence and exact changed/addition lists (`manage.py:120–143`). Production preflight rechecks local/remote backup and source evidence, including mutable tags.
- PASS: active deployment preserves original headers, custom metadata and tags, uses conditional PutObject, writes assets before HTML/home, and journals returned versions. Invalidation includes only changed keys and directory aliases (`manage.py:169–204`, `_release_guard.py:225–245`).
- PASS: the adapter overrides the inherited deletion-capable rollback with conditional zero-delete restore; additions remain unreferenced and terminal restore prevents redeployment (`manage.py:173–189`). No settings/permission mutations are implemented.
- Operations test-matrix rows are covered by a versioned S3 fake, real temporary files, drift/tamper/path guards, route invalidation, and read-only 527-object public evidence. Real destination-copy verification remains the next integration step, rather than being claimed as completed.

## Adversarial Findings

No unresolved P1/P2 findings in the frozen operations code.

The initial review run exposed a failing empty-tag-value test caused by the fake dropping blank URL-encoded values. The coder corrected `parse_qsl(..., keep_blank_values=True)` and retained both the tag assertion and authenticated-verifier assertion. The final independent run passes. The realistic Expires datetime roundtrip is also tested; canonical header conversion prevents JSON/datetime mismatch during verification.

Checked source same-body new-version changes, tag changes without new versions, metadata/header drift, local content mismatch, wrong distribution alias/origin, tampered remote backup bodies/manifest, incomplete approval evidence, altered build scope, symlinks/traversal, additions during restore, and terminal restore. Backup source writes and active deletion calls are absent. The fake does not prove AWS service semantics; real versioned copies must still pass the adapter's destination verification and completion receipt.

Partial multi-object deployment is not atomic. A successful remote write with a lost response can create an unjournaled version; the guard stops rather than overwriting it. Retained versions and the remote backup permit deliberate recovery. Do not bypass that halt or claim automatic atomic rollback.

## QA Verification

- PASS: `python3 -m unittest discover -s hookedaz-review/operations/tests -v` — **28 tests passed**, independently rerun after the source freeze.
- PASS: `python3 -m py_compile hookedaz-review/operations/manage.py hookedaz-review/operations/_release_guard.py`.
- PASS: code inspection of backup destination boundaries, pinned bodies/settings, remote manifest integrity, exact approval binding, selected uploads, zero-delete adapter restore, and scoped invalidation.
- NOT RUN here: authenticated destination copies, production preflight/upload/restore, final site public verification. Root must run backup integration now and final release acceptance after site approval.
- Brand/accessibility/UI validators: not applicable to this operations-only Python component. Main site review must run the applicable UI checks separately.

Reviewed SHA-256:

| File | SHA-256 |
|---|---|
| `manage.py` | `c656f1d4e3e2a8a1a439d48687790848aa94452bf1653812e810e6ee1be8ba98` |
| `_release_guard.py` | `c902f92c1fecc1bb369600194f494a4f3639995cb49af98680bb4269da4b05b1` |
| `tests/test_manage.py` | `ccb7dd36f3caf928e8b8569af5a4c6adac3db3ee3cbd0690ee221c0f6f13cc8d` |

## Code Quality

1. **Structure:** backup, frozen preparation, and release adaptation have explicit responsibilities; reuse is limited to a local reviewed core.
2. **Naming:** target constants and command modes are clear; compact helper names remain understandable in this private operational tool.
3. **Error handling:** drift and missing evidence fail closed with identifying context. Failed state is retained for diagnosis rather than overwritten.
4. **Organization:** adapter, core, tests, and private state are separated; operation paths do not depend on another archive's live constants.
5. **Documentation:** README explains exact runtime, private-state handling, hashes, integration gates, cache status, and recovery limits.
6. **Testing quality:** tests assert stored bodies/tags/headers, current versions, no source mutation during backup, and no deletion during adapter restore, rather than merely mocking the system under test.
7. **Testability/seams:** the injected S3/CloudFront clients and temporary filesystem are appropriate minimal seams. Real integration remains necessary for provider assumptions and is explicitly guarded by remote verification.

## Assessment: APPROVED

Approved for the version-pinned remote backup step using the reviewed operations code. Production payload deployment remains gated on independent site review, matching build/validation hashes, verified backup completion, and fresh source preflight.
