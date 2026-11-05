# HookedAZ repairs deployed

The approved non-video repairs are live at [HookedAZ](https://hookedaz.cronkitenewsonline.com/), verified November 5, 2026. The source is published on [`codex/hookedaz-archive-repairs`](https://github.com/cronkite-asu/HookedAZ/tree/codex/hookedaz-archive-repairs) in the maintained cronkite-asu repository. Its `master` preserves upstream commit `dcc28780808f232fc51ce61e3008d6d6751ed551` from [cronkite-news/HookedAZ](https://github.com/cronkite-news/HookedAZ).

## Result

The archive retains all 527 original object keys, photographs, binary assets, data files, article paragraphs and captions. Forty HTML files were repaired and two shared assets were added, for **529 current objects**. YouTube, Vimeo and SoundCloud iframe addresses and existing attributes remain preserved. Video identity/availability issues await the owner's media-account access.

Repairs cover map loading/legends/markers/tab resizing, exact data tables and keyboard controls, mobile navigation, archive context, closed submissions, stale resource/download notices, image and iframe alternatives, gallery/animation alternatives, UTF-8, and copied metadata. The decorative background uses its original static poster. No objects were deleted, and no AWS permissions or shared configuration were changed.

Implementation commit: `3227c68`. A separately reviewed five-parent cache correction is commit `4745d1c`.

## Verified backups

Both backups are version-pinned copies with remote SHA-256, content headers, custom metadata and tags verified. Source current versions remained unchanged while each backup was made. Manifest and completion records are stored alongside the backed-up `site/` tree.

| Stage | Objects / bytes | Backup prefix |
|---|---|---|
| Before any repair | 527 / 104,986,994 | `s3://datasync-efs-shared-1.jmc.asu.edu/hookedaz.cronkitenewsonline.com/20261105T223940Z-before-repairs-75086b745a07/` |
| Before cache correction | 529 / 105,052,107 | `s3://datasync-efs-shared-1.jmc.asu.edu/hookedaz.cronkitenewsonline.com/20261105T225739Z-before-repairs-464e1a66891f/` |

Original backup manifest SHA-256: `5d326ffdc3fc8451567be30c58b4c9ab6f471d3630dd6b2766610b5528b6d5e4`.

Follow-up backup manifest SHA-256: `f9094e6040732574d1091ff677917337fda9d00705fdf52bf93c5b1cb2e77f42`.

The original 527-object `site/` tree is the baseline required by [the preservation builder](README.md). Download into a new empty local directory and verify it against `baseline-manifest.json`; do not substitute the current repaired production tree.

## Guarded releases and cache acceptance

The first release, `bd0d153b-e9f3-47fb-8c10-02645e14d173`, conditionally wrote 40 HTML objects and two new assets. Its 101-path invalidation completed. All 529 authenticated object checks and 560 public file/directory/404 checks passed.

The returning review browser still reused old internal iframe documents after parent revalidation, despite correct server bytes. The follow-up adds `archive=20261105-r2` to ten same-site iframe references across five parent pages. It changes no child file, shared asset, external-media address, or other object. Release `7c43331c-39ce-4572-bd92-ce41315bf130` conditionally wrote exactly those five HTML objects; its 13-path invalidation completed.

Final results:

- **529/529 authenticated object checks passed**, including preserved content headers, custom metadata and tags for the selected writes.
- **560/560 public checks passed**, including every object, directory routes and a real missing-page 404 control.
- **9/9 distinct versioned internal iframe URLs** returned the exact reviewed child bytes.
- The same returning browser loaded the repaired chart and all five map views/tables after reloading only the parent. It also loaded the versioned effects and gallery frames with their alternatives.
- Live 320px navigation wrapped correctly; About reached its page and submissions remained clearly closed.

Final build-manifest SHA-256: `77b54844ffbe4a18b0c691bfc6b9861315c97b41782fdc9855f3d03901749a0e`.

Final validation SHA-256: `a2f8819cf0007107c7383cac5b40bc6137a6bd77e55553c871525e114fb35af8`.

Future changes to internal embedded HTML require a revision bump and deployment of the affected parent pages, as documented in [README.md](README.md).

## Review and recovery evidence

Independent verification passed **18 Python site tests, three Node controller tests, and 28 operations tests**. The original and cache reviews approved exact frozen build/validation hashes. A nonblocking suggestion to tighten semantic mutation assertions is retained in the original review.

- [Original independent review](review/review-report.md)
- [Cache correction review](review/cache-review-report.md)
- [Local browser acceptance](review/browser-qa.md)
- [Live browser acceptance](review/live-qa.md)
- [Final public verification](review/public-verification.json)
- [Final authenticated verification](review/object-verification.json)
- [Versioned embed URL verification](review/query-verification.json)
- [Guarded operations and restoration](operations/README.md)

Private backup receipts, version IDs, frozen release inputs and journals remain outside the public repository in `hookedaz-review/operations-state/` and `hookedaz-review/operations-state-cache-fix/`. The guarded `restore` operation restores changed original objects from those records and retains unreferenced additions without deleting them. No restoration was needed or executed.

Targeted accessibility improvements were verified; complete WCAG conformance, actual screen-reader speech, genuine 200% browser zoom, OS forced-colors behavior, every photo/popup and complete third-party media playback are not claimed.
