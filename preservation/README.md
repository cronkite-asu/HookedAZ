# HookedAZ preservation build

This directory maintains the static 2015 HookedAZ archive for readers and archive maintainers. It is part of the maintained [cronkite-asu copy](https://github.com/cronkite-asu/HookedAZ), based on [cronkite-news/HookedAZ](https://github.com/cronkite-news/HookedAZ) `master` commit `dcc28780808f232fc51ce61e3008d6d6751ed551`.

The live S3 snapshot includes media updates absent from the older Jekyll source. Use this preservation build for deployment: rebuilding the Jekyll authoring files would restore old content and video URLs. The original authoring tree is retained for historical reference; `_config.yml` excludes this maintenance directory from Jekyll output.

## Build and check

Use Python 3.12 or newer and Node.js. No third-party Python package or frontend build system is required. Run from the repository root:

```sh
python3 preservation/build.py --baseline ../live-s3 --output ../build
python3 preservation/validate.py --baseline ../live-s3 --build ../build
python3 -m unittest discover -s preservation/tests -v
node --test preservation/tests/*.test.mjs
python3 -m http.server 8765 --bind 127.0.0.1 --directory ../build
```

The preview is at [localhost:8765](http://127.0.0.1:8765/). Stop it with Ctrl-C.

`../live-s3` must be the complete original 527-object S3 snapshot, recovered from the verified backup when necessary. A loose `aws s3 sync` from the repaired production bucket is **not** the original baseline. `baseline-manifest.json` checks every original object's SHA-256 before the builder writes output. `baseline/` retains the original 110 small HTML/script/style/data/text files with byte-preserving Git attributes; binary assets remain in the complete backup. Source bucket and upstream provenance are recorded in the manifest. No original PHP or Jekyll dependencies need to run.

The builder copies original objects byte for byte, transforms the HTML explicitly, and adds only `assets/archive.css` and `assets/archive.js`. The built site has 529 objects, keeps all original keys and data files, and does not replace YouTube, Vimeo, or SoundCloud source attributes. Build output and the generated validation manifest remain untracked. The validator records full build hashes, original hashes, the exact changed/added keys, and failures. Any failure blocks release.

Internal iframe URLs carry the deterministic `archive` revision from `repairs.json`. This makes repaired parent pages request fresh map, chart, gallery and effects documents when returning browsers still cache the older child HTML. Other query parameters and fragments are retained; external media URLs are unchanged. Bump `internal_frame_revision` whenever a later repair changes embedded internal HTML, and rebuild/deploy every affected parent page together with the children.

## What the overlay repairs

- Adds publication context and retires unavailable submissions without adding a new collection service.
- Marks parked, missing, and misdirected historical resources/downloads unavailable while retaining their labels and reporting.
- Restores Leaflet imports, county initialization, HTTPS map tiles/attribution, map resizing after tab switches, and local point icons for maps whose original marker PNGs were missing.
- Adds exact original data tables with suppression labels intact. Race/gender controls are native buttons.
- Repairs mobile About/navigation, hidden menu state, Escape/focus handling, skip links, headings, image alternatives from publication captions, and iframe titles.
- Preserves the effects animation and photo gallery, with text/caption alternatives, and replaces the missing history iframe with an unavailable notice.
- Corrects inherited sharing attribution, font URLs, legacy responsive-script paths, and the homepage's previously unclosed script. The decorative hero uses its original static poster; its video sources and files remain preserved without automatic motion.

New controls and notices use native HTML and approved ASU web token colors. The existing Bootstrap 3 archival presentation is retained; Unity adoption would change the historical design and introduce Bootstrap 5/build dependencies. The new stylesheet uses explicit 16px/24px font equivalents because Bootstrap 3 sets the root to 10px. Original imagery, stylesheet files, and JavaScript libraries are unchanged.

## Validation and release

Python integration tests operate on the actual snapshot, check deterministic output, and attack baseline drift, output symlinks, changed media, lost paragraphs, and altered suppressed counts. All generated inline scripts are syntax-compiled with Node. Node tests exercise menu state, Escape/focus return, section-link focus, and unavailable/same-origin map-frame callbacks. Static tests complement direct browser checks; they do not establish WCAG conformance or complete media playback.

Use the [guarded operations tools](operations/README.md) for backup, frozen release preparation, preflight, selected writes, verification, and recovery. The release requires an independently approved report bound to the exact validation/build hashes and a verified backup in the owner-specified bucket. Do not upload this repository wholesale, delete old objects, or change shared CloudFront/bucket permissions to apply these repairs. Only the built site belongs in the website bucket.

If the baseline hash check fails, stop and investigate source drift. If the original archive backup cannot be recovered, do not manufacture a replacement baseline from mismatched Jekyll output. If an external service or map tile endpoint later fails, the added tables and historical notices still provide readable content; recover original media/resources only when their identity is verified.
