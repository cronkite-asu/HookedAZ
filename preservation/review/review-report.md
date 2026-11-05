# HookedAZ independent final review

Reviewed November 5, 2026 against `.pipeline/design-doc.md`, `.pipeline/impl-report.md`, `.pipeline/browser-qa.md`, the actual preservation code and generated release tree. Scope is the user-approved non-video repair plan. Existing YouTube/Vimeo/SoundCloud iframe source attributes remain unchanged.

## Spec Compliance

| Requirement / test-matrix group | Assessment and evidence |
|---|---|
| Current S3 source of truth and reproducible overlay | PASS: `preservation/build.py:274–290` verifies all 527 baseline hashes and tracked text inputs, rejects symlinks/unsafe output locations, copies original files and transforms keyed HTML. Two real builds have identical hashes. Legacy Jekyll excludes `preservation`; byte-preserving Git attributes cover tracked baseline inputs. |
| Preserve keys, original assets, reporting and media | PASS: independent validator checks original key retention, every unchanged non-HTML byte hash, image-reference multiplicities, original media attribute sets and paragraph/caption text (`validate.py:38–59`). The actual release retains all 527 keys, changes 40 HTML files and adds only two shared assets: 529 output objects, zero deletions. |
| Resources, historical context and feedback retirement | PASS: explicit dispositions retain historical names/reporting, annotate parked/missing/misdirected resources and unavailable downloads, remove PIN scripts/modals/active calls, and preserve readable closed-submission URLs. No new clinical advice, form recipient or collection backend is introduced. |
| Maps/chart and faithful data alternatives | PASS: local Leaflet replaces HTTP loaders; county duplicate/dead marker block is removed; map tiles use HTTPS and attribution. Point markers use local DivIcons, visibility/resize callbacks resize same-origin maps, and exact source arrays/GeoJSON generate scoped semantic tables. County tables use reported `Overdose` labels rather than hidden numeric classes. Original data files remain byte-identical. |
| Navigation and accessibility | PASS for the specified repairs: named native menu buttons, hidden/inert closed panel, Escape/opener focus, mobile About/wrapping, focusable skip/main target, native chart/disclosure controls, keyboard tab selection, image alternatives from retained captions, titled frames, zoom restoration and heading repairs. Runtime menu tests and root's actual keyboard/map journeys complement static markup tests. |
| Legacy missing content and archival presentation | PASS: missing history frame becomes an unavailable notice; missing script/favicon references are resolved or removed; sharing attribution/fonts/UTF-8 are repaired. Effects/gallery assets and original imagery remain. New UI uses approved tokens/native markup without a Bootstrap/Unity migration. Root approved static decorative hero poster while retaining original video files/source URLs. |
| Backup and guarded release | PASS at the reviewed tooling/evidence boundary: operations adapter remains byte-identical to the separately approved code and all 28 vendored tests pass. The completed receipt covers 527 objects/104,986,994 bytes, verified destination SHA/metadata/tags and unchanged source versions at `s3://datasync-efs-shared-1.jmc.asu.edu/hookedaz.cronkitenewsonline.com/20261105T223940Z-before-repairs-75086b745a07/`. Final upload still requires frozen exact-build preparation and fresh source/backup preflight. |

All design test-matrix groups have corresponding automated or actual-browser evidence. Real filesystem inputs and a small DOM event-boundary fake match the design's seam strategy. No additional runtime service/framework or video replacement was introduced.

## Adversarial Findings

No unresolved P1/P2 findings in the frozen payload or active operations adapter.

- **[P3] Make semantic mutation expectations explicit in the regression assertion.** `preservation/tests/test_build.py:137–151` currently asserts that mutation produces any validation failure. Exact-output checks could continue satisfying that assertion if a future change weakens independent semantic checks. Prefer asserting the relevant `Original paragraph/caption lost`, media-attribute, and reported-table failure categories. This is nonblocking: the reviewer separately removed an actual original article paragraph exceeding 150 characters from a temporary copy and confirmed the independent semantic error, beyond the deterministic output mismatch.

Additional adversarial checks covered a changed documentary ID, a changed suppressed county label, modified baseline/output symlink, actual missing reporting, preserved binary/data hashes, all inline script syntax, exact additional-key set, immutable media attributes and changed approval/build evidence. Original content and GeoJSON are parsed as data rather than evaluated. New table/alternative values are HTML-escaped.

Operations drift/tamper tests cover same-body new versions, mutable tags, timestamp headers, remote backup corruption, wrong alias/origin, changed scope, path traversal, source changes before upload, and zero-delete restore. The SDK field contract was checked locally by the operations agent; the completed real backup supplies the provider integration evidence. A multi-object release is not atomic; retained versions and the guarded journal remain the recovery boundary. Do not bypass an unjournaled-change halt.

## QA Verification

Independent commands and results:

- `python3 -m unittest discover -s preservation/tests -v` — **16 passed**, including real snapshot builds and inline scripts compiled with Node.
- `node --test preservation/tests/*.test.mjs` — **3 passed**: single menu toggle, hidden/inert and Escape focus, section-link focus, and safe frame callback behavior.
- `python3 -m unittest discover -s preservation/operations/tests -v` — **28 passed** against the copied operational code.
- `python3 -m py_compile preservation/build.py preservation/validate.py` — PASS.
- `python3 preservation/validate.py --baseline ../live-s3 --build ../build --output /tmp/hookedaz-reviewer-validation.json` — zero failures; independently generated JSON is byte-identical to the frozen validation file.
- `python3 /Users/jleggat/.agents/skills/asu-brand-web/scripts/validate-brand.py preservation/assets/` — zero errors/warnings for the new stylesheet; JavaScript correctly out of scope. Legacy archival styles are preserved under the explicit design exception, rather than represented as newly brand-compliant.
- Accessibility skill heuristic against the explicit **40 generated HTML files** — zero findings. The unchanged vendor JavaScript is outside this generated-HTML scan.
- Independent original-prose removal probe — PASS: removing a real original paragraph from a temporary full build yields `Original paragraph/caption lost` for the affected article.
- Baseline/build hashes and exact delta — PASS: 40 changed original HTML keys, only `assets/archive.css` and `assets/archive.js` added, no deleted keys.

Browser acceptance is root's direct CUA evidence in `browser-qa.md`, not a fabricated reviewer rerun: 320px/1280px layouts, mobile menu/skip/Escape/About, every map tab and chart keyboard control, exact table display, marker popup/zoom/fullscreen, retired feedback/resources, gallery alternative, effects animation/text and unavailable history. Root corrected and retested actual browser-discovered script, contrast, disclosure, marker and charset defects before freezing this build.

No `agent-browser` skill is installed; browser journeys were performed through CUA by root. Actual screen-reader speech, genuine 200% zoom, OS forced-colors behavior, every popup/slide and complete third-party media playback remain unrun and documented. Static/targeted checks do not establish complete WCAG conformance. Existing broken video media remain intentionally pending account access. Live deployment/public hashes must be verified after the guarded upload.

## Code Quality

1. **Structure:** a deterministic static builder, separate semantic validator, small shared controller, and isolated operations adapter separate concerns without introducing a new framework.
2. **Naming:** transformations and map/data roles are explicit. Shared constants enumerate exact assets/maps rather than hiding broad writes.
3. **Error handling:** source drift, unknown data/anchors, overlapping edits, symlinks, invalid builds and operational evidence mismatches fail closed. Third-party frame access failures are narrowly caught.
4. **File organization:** tracked input provenance, code/assets/tests and ignored output/private state are distinct. Original authoring content remains historically intact.
5. **Documentation:** README describes the authoritative baseline, actual runnable build/test commands, archival scope, recovery and guarded operations. The implementation/browser reports distinguish completed checks from limits.
6. **Testing quality:** tests exercise real filesystem snapshots, generated markup/scripts and mutation failures. Browser evidence covers behaviors the minimal DOM fake cannot establish. The P3 assertion improvement above would strengthen future test fidelity.
7. **Testability/seam quality:** real local inputs are used where safe and deterministic; the minimal injected DOM/client seams cover state/provider boundaries without interface ceremony or mocking the builder/validator under test.

## Assessment: APPROVED

Approved for the exact frozen static payload below, subject to the existing guarded prepare/preflight/upload and post-deployment acceptance steps. No additional user confirmation is required by this review.

Validation SHA-256: a4bd3147d202b00de3bc77396f8d5f406ca17bbe6726a76c63b81269eeaaeefb

Build manifest SHA-256: 95e9d9b42068c3013ce6df5cf5f897d2fb145a4cd72d686eef6bb504e67f9137

The build digest is SHA-256 of UTF-8 `json.dumps(build_sha256, sort_keys=True, separators=(',', ':'), ensure_ascii=True)`. Rebuild changes invalidate this approval unless the exact validated hashes remain identical.
