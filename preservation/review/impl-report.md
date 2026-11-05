# HookedAZ non-video implementation report

Status: **DONE_WITH_CONCERNS** — implementation and local validation complete; independent review and production operations remain root's acceptance gates. Full screen-reader speech, genuine browser 200% zoom and forced-colors mode are not claimed.

## What was implemented

The requested branch is `codex/hookedaz-archive-repairs`, based on upstream `master` at `dcc28780808f232fc51ce61e3008d6d6751ed551`. Site changes live under `repo/preservation/`; the original Jekyll authoring files remain historical and `_config.yml` excludes preservation tooling from Jekyll output. Root is publishing the maintained copy to cronkite-asu rather than the read-only original organization.

The stdlib Python builder checks all 527 baseline object hashes and tracked text inputs, copies the complete current S3 snapshot, and explicitly transforms the 40 HTML pages. It retains all original keys, binaries, data files, photo references, reporting paragraphs/captions and existing YouTube/Vimeo/SoundCloud iframe attributes. Only two keys are added: `assets/archive.css` and `assets/archive.js`. Output contains 529 files; 40 original HTML files change; no original key is deleted. The checked-in 110-file text snapshot has Git `-text` attributes for byte-preserving fresh checkouts.

Implemented archive notices, historical resource/unavailable-download labels, removal of PIN collection scripts/modals/actions, closed feedback pages, local Leaflet imports, county initialization fix, HTTPS tiles with attribution, same-origin map resizing after tabs, and local DivIcon point markers for missing default PNGs. Exact arrays/GeoJSON generate semantic table alternatives without exposing county suppression classifier values. Race/gender buttons expose pressed state.

Implemented mobile About, wrapped menu labels, named native menu controls, initially hidden/inert closed panel, Escape/focus return, section-link focus, skip links/main target, names/titles/alt from published captions, topic/byline hierarchy, native mobile data disclosure and keyboard data-tab selection. Gallery alternatives retain all image captions; animation text is extracted from the original animation source and placed beside its frame. Missing history content gets an unavailable notice. Corrected copied sharing attribution, HTTP fonts, favicon/missing wrapper-script dependencies, and original homepage's unclosed script. A meta UTF-8 declaration is ensured early in every document.

New notices use approved ASU token colors and native HTML; preserving the Bootstrap 3 historical design avoids a framework migration. Readable notice/hero type uses 16px/24px equivalents because Bootstrap's root is 10px. Hero text has an opaque light surface and dark text. With root's approval, decorative hero autoplay/loop is removed and its existing snowfall poster is used; original video files/source URLs remain. Reduced-motion CSS/controller behavior is also present.

## TDD evidence

### Tests and seams

- `repo/preservation/tests/test_build.py`: 16 integration/regression tests over the real 527-object snapshot and real temporary build trees. Tests inspect actual HTML and preserved resources; malicious mutation tests exercise media drift, a missing paragraph and altered suppressed count. Baseline changes/output symlinks are rejected. Builds are deterministic.
- `repo/preservation/tests/archive.test.mjs`: three runtime tests using a small DOM fake only at the menu/frame event boundary; real browser QA remains necessary. Tests exercise single toggle, hidden/inert state, Escape/opener focus, section focus and safe map-frame callbacks.
- Every generated inline script in all 40 pages is syntax-compiled with the real Node `vm.Script` API; this reproduced the original homepage's unclosed-script defect before repair.
- `repo/preservation/validate.py`: actual release-tree semantic comparisons, independent source paragraph/image/media checks, exact reported table cell comparisons, internal references and expected transformed-byte checks. No external service mock is used for local preservation checks.

### RED

From `hookedaz-review/repo`:

`python3 -m unittest discover -s preservation/tests -v` initially ran the real original snapshot: 10 tests, nine expected failures (dead PIN loader, HTTP/missing map initialization, old anchor controls, bad resource destinations, absent alternatives/tables/validator). The unchanged-key/binary/data/media preservation test passed. Evidence: `site-red.log` beside this report.

`node --test preservation/tests/*.test.mjs` initially failed because the controller module did not exist. Evidence: `site-js-red.log`.

Additional narrowly reproduced RED cycles, all before their corresponding production fixes:

- `python3 -m unittest discover -s preservation/tests -k all_inline -v`: unmatched script count on homepage; `site-inline-red.log`.
- `... -k mobile_data -v`: no native data disclosure button; `site-data-disclosure-red.log`.
- `... -k maps_bootstrap -v`: missing local DivIcon/point-to-layer fallback; `site-marker-red.log`.
- `... -k hero_text -v`: absent opaque contrast surface; `site-hero-red.log`.
- `... -k animation_alternative_is -v`: alternative appended after footer; `site-animation-placement-red.log`.
- `... -k decorative_hero -v`: inherited autoplay/loop; `site-decorative-motion-red.log`.
- `... -k every_html -v`: direct hospital map lacked UTF-8 declaration; `site-charset-red.log`.

### GREEN

Commands run from `hookedaz-review/repo`:

```sh
python3 preservation/build.py --baseline ../live-s3 --output ../build
python3 preservation/validate.py --baseline ../live-s3 --build ../build
python3 -m unittest discover -s preservation/tests -v
node --test preservation/tests/*.test.mjs
python3 -m py_compile preservation/build.py preservation/validate.py
python3 /Users/jleggat/.agents/skills/asu-brand-web/scripts/validate-brand.py preservation/assets/
```

Final results: 529 files, validator `failures: []`, 40 changed keys and two additions; **16 Python tests pass** in 26.893 seconds; **three Node tests pass**; Python compilation passes; brand scan has zero errors/warnings (CSS checked, JavaScript correctly out of scope).

The accessibility heuristic was run with the explicit 40 generated HTML paths rather than unchanged vendor scripts: **zero heuristic findings**. Earlier broad-directory scan matched an embedded `<html>` string in original jQuery and inherited decorative autoplay; the former was narrowed to actual HTML and the latter repaired. Logs: `site-green.log`, `site-js-green.log`, `site-brand.log`, `site-a11y.log`.

No standalone refactor phase was performed. Source changes were small behavior repairs driven by failing tests and browser findings; no framework/library upgrade was introduced.

### Browser and unrun checks

Root separately performed actual CUA preview acceptance: 320px mobile menu/wrapping/About, Escape/focus, first skip link to main, mobile data disclosure, all data tabs and chart controls, map markers/popups/zoom/fullscreen, resource/feedback/history notices, gallery/images and effects animation/text. Root records those observations independently. The last direct-page charset issue is fixed with a regression and the new build is ready for final retest.

Not run by this agent: axe, screen-reader speech, genuine 200% zoom, OS forced colors, comprehensive media playback, production deployment or post-deployment verification. YouTube/Vimeo defects remain intentionally pending account access. Existing historical libraries and editorial wording are retained. Neither passing static tests nor added alternatives claims complete WCAG conformance.

## Frozen paths and hashes

- Complete immutable baseline: `hookedaz-review/live-s3/` (private external tree).
- Build: `hookedaz-review/build/`.
- Validation: `hookedaz-review/repo/preservation/validation.json`.
- Operations implementation/backup/release reports: separate operations-agent ownership.

Validation SHA-256: a4bd3147d202b00de3bc77396f8d5f406ca17bbe6726a76c63b81269eeaaeefb

Build manifest SHA-256: 95e9d9b42068c3013ce6df5cf5f897d2fb145a4cd72d686eef6bb504e67f9137

The manifest digest is SHA-256 of UTF-8 `json.dumps(build_sha256,sort_keys=True,separators=(',',':'),ensure_ascii=True)`. Do not release a different manifest under this report.

## Files changed

- Repository `.gitignore`, `.gitattributes`, `_config.yml`.
- `preservation/baseline-manifest.json` and 110 `preservation/baseline/` input files.
- `preservation/build.py`, `validate.py`, `repairs.json`, `README.md`.
- `preservation/assets/archive.css`, `archive.js`.
- `preservation/tests/test_build.py`, `archive.test.mjs`.
- This report and private TDD logs under `hookedaz-review/.pipeline/`.

Operations agent separately owns `preservation/operations/` and all backup/release code/receipts. No source commit, push, AWS write or deployment was performed by the site implementation agent.
