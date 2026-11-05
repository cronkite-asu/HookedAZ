# HookedAZ internal-frame cache follow-up review

Reviewed November 5, 2026 against `cache-design-doc.md`, `cache-impl-report.md`, the actual implementation/tests and the frozen first-release/follow-up trees. This approval is separate from the historical first-release approval.

## Spec Compliance

- PASS: `preservation/build.py:62–75` appends the configured stable revision only to internal iframe sources. Relative/root-relative URLs and the exact same-site hostname are recognized; external hosts and non-HTTP schemes are excluded. Existing non-archive query parts and fragments survive, prior archive values are replaced, and repeat transformation is idempotent.
- PASS: exact raw-byte comparison against `operations-state/build` proves only `?archive=20261105-r2` is inserted in five parent HTML files. Removing that insertion reproduces each first-release file byte for byte. There are **zero added/deleted objects** and the total remains **529**.
- PASS: affected parents are `data/index.html`, `interactives/effects.html`, `how-heroin-affects-the-body/index.html`, and the couple/treatment article gallery parents. Ten iframe references cover nine distinct child URLs. Every child document, shared CSS/JS, binary/data file and unrelated page remains byte-identical to release 1. External YouTube/Vimeo/SoundCloud attributes remain unchanged.
- PASS: configuration/README explain the deterministic revision and future bumps. The follow-up uses its own build, validation, current-529-object backup and release state; release 1 artifacts remain intact.
- PASS at the evidence boundary: the fresh completion receipt covers 529 current objects with SHA/header/metadata/tag verification and unchanged source versions under `s3://datasync-efs-shared-1.jmc.asu.edu/hookedaz.cronkitenewsonline.com/20261105T225739Z-before-repairs-464e1a66891f/`. The approved operations adapter is unchanged. Guarded prepare/preflight remain mandatory before the five selected writes.

## Adversarial Findings

No P1/P2 findings in this isolated follow-up.

Reviewed exact-host comparison against a deceptive hostname suffix, preservation of unrelated percent-encoded query text/fragments, replacement of an existing archive parameter, repeated transformation, exclusion of external media and preservation of original child paths. The release validator resolves internal files by URL path, so the revision cannot conceal a missing dependency. HTMLParser attribute decoding and escaped output avoid treating `&amp;` as a literal query-key fragment.

The new query selects a fresh browser document URL; it does not claim to purge a user's browser cache. Root must verify the returning browser's original failing parent journey after upload. No CloudFront policy/permissions/origin changes or external video fixes are included.

## QA Verification

Independently rerun:

- Full Python suite: **18 passed** in 25.545 seconds, including both new cache tests and all preservation/data/menu/script regressions.
- Node controller suite: **3 passed**.
- Python compilation for builder/validator: PASS.
- Follow-up validator: zero failures; reviewer-generated validation JSON is byte-identical to the frozen file.
- Exact first-release/follow-up filesystem comparison: only five declared parent files differ; stripping the new query bytes gives exact old bytes. No additions/deletions, child/asset changes or unrelated output changes.
- Accessibility heuristic on the five affected generated HTML files: zero findings. Shared CSS/runtime code and historical presentation are byte-identical to the already reviewed release; no repeated brand scan is needed for this URL-only delta.
- Root integration evidence `operations/cache-query-proof.json`: all nine distinct versioned child URLs passed public HTTP verification. The root reports exact reviewed child-body matches; the saved compact result records the nine successful URL checks.
- Operations source hashes still match the separately approved code: adapter `c656f1d4e3e2a8a1a439d48687790848aa94452bf1653812e810e6ee1be8ba98`, core `c902f92c1fecc1bb369600194f494a4f3639995cb49af98680bb4269da4b05b1`.

Not yet run by reviewer: live returning-browser acceptance of deployed parents, final authenticated/public verification and cache-invalidation completion. Those remain root's post-upload acceptance gates. Existing screen-reader/zoom/forced-colors and third-party playback limits from the first review remain unchanged.

## Code Quality

1. **Structure:** one focused transformation and one configured revision; no new runtime subsystem.
2. **Naming:** helper and configuration express internal-frame revision purpose.
3. **Error handling:** existing baseline/build validation and release drift gates remain intact; unsupported/external sources are left unchanged.
4. **Organization:** separate follow-up artifacts preserve the first release and its recovery record.
5. **Documentation:** supplemental design and README explain browser-cache intent, revision bumps and exact scope.
6. **Testing quality:** real generated files establish ten internal references and valid paths; focused fixtures verify query/fragment/external-host/idempotence behavior. Full regression suites still exercise original reporting/data/media preservation.
7. **Testability/seams:** pure URL/HTML transformation is tested directly, with real filesystem comparison and real child HTTP evidence; no browser-cache behavior is falsely proved by mocks.

## Assessment: APPROVED

Approved for the exact frozen follow-up payload, subject to fresh guarded preflight, conditional selected uploads, and live returning-browser/public acceptance.

Validation SHA-256: a2f8819cf0007107c7383cac5b40bc6137a6bd77e55553c871525e114fb35af8

Build manifest SHA-256: 77b54844ffbe4a18b0c691bfc6b9861315c97b41782fdc9855f3d03901749a0e

The build digest uses SHA-256 of UTF-8 sorted compact JSON with `ensure_ascii=True`, as required by the operations guard. A different frozen payload requires another hash-bound assessment.
