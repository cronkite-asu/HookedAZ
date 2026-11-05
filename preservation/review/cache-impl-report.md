# Internal-frame cache follow-up

Status: **DONE** — implementation and tests complete, frozen for independent review. Production release 1 is preserved; this follow-up writes only a separate build and validation file. No AWS actions were performed by this agent.

## Closure table prepared before implementation

| # | Finding | Severity | Type | Files | Planned fix | Evidence type | Verify command | Result |
|---|---|---|---|---|---|---|---|---|
| 1 | Returning browsers reuse old internal iframe documents even when repaired parent HTML is fresh | P1 | AUTO | preservation/build.py, repairs.json, tests/test_build.py, README.md | Add a deterministic archive revision query to same-site frame URLs only; preserve paths, other query parameters/fragments, and all external media attributes | red-test, green-test, integration | Targeted internal-frame tests, full Python/Node suites, separate-build validator | Two expected RED failures; targeted two pass; full 18 Python and three Node pass; validator failures empty; exact five-parent-only live delta |

## What changed

`version_internal_frames()` versions only relative, root-relative and absolute same-site iframe URLs. It adds the configured `archive=20261105-r2` exactly once, preserves other query text and fragments, and leaves external origins untouched. A preexisting `archive` parameter is replaced rather than duplicated. The tests explicitly exclude a deceptive hostname suffix and verify idempotence. No runtime code or CloudFront configuration changed.

`repairs.json` owns the deterministic revision. `README.md` instructs maintainers to bump it when later internal child HTML changes, rebuilding and deploying affected parents together. `.gitignore` excludes the separate validation artifact.

The follow-up build still comes from the original authoritative 527-object snapshot. Relative to release 1's frozen 529-object build, only these five parent HTML files change:

- `data/index.html` — six data frames.
- `interactives/effects.html` — effects frame.
- `how-heroin-affects-the-body/index.html` — effects frame.
- `for-one-couple-staying-sober-is-the-key-to-their-relationship/index.html` — gallery frame.
- `young-white-suburban-plus-risk-taking-behavior-makes-getting-addicts-into-treatment-difficult/index.html` — gallery frame.

There are zero additions/deletions relative to production release 1. Every child document, all binary/data files and both shared assets are byte-identical to release 1. External YouTube/Vimeo/SoundCloud iframe attributes and reporting remain preserved.

## TDD and verification

Commands run from `hookedaz-review/repo`:

```sh
python3 -m unittest discover -s preservation/tests -k revision -v
python3 preservation/build.py --baseline ../live-s3 --output ../build-cache-fix
python3 preservation/validate.py --baseline ../live-s3 --build ../build-cache-fix --output preservation/validation-cache-fix.json
python3 -m unittest discover -s preservation/tests -v
node --test preservation/tests/*.test.mjs
python3 -m py_compile preservation/build.py preservation/validate.py
```

RED: the two new tests failed because the helper did not exist and actual internal iframe URLs lacked the revision. Evidence: `cache-red.log` beside this report.

GREEN: targeted two pass; full **18 Python tests pass in 26.841 seconds**; **three Node tests pass**; Python compilation passes. Validator reports `failures: []`. The complete suite still checks original external media attributes, all original keys/data/binaries, deterministic output, reported counts and original prose. Logs: `cache-targeted-green.log`, `cache-green.log`, `cache-js-green.log`.

No structural refactor occurred. Root retains live returning-browser acceptance and independent review ownership. Actual browser-cache eviction behavior was not simulated with mocks or claimed proven by the unit tests; it must be checked using the returning live browser that reproduced the stale iframe documents.

## Frozen artifacts

- Build: `hookedaz-review/build-cache-fix/`.
- Validation: `hookedaz-review/repo/preservation/validation-cache-fix.json`.
- Release 1 build/validation were not modified.

Validation SHA-256: a2f8819cf0007107c7383cac5b40bc6137a6bd77e55553c871525e114fb35af8

Build manifest SHA-256: 77b54844ffbe4a18b0c691bfc6b9861315c97b41782fdc9855f3d03901749a0e

The canonical manifest digest uses sorted compact JSON with `ensure_ascii=True`, matching the approved operations guard. No source commit, push or deployment was performed by this agent.
