# Internal embed cache follow-up

This is a correction within the approved deployment/cache-verification scope. The first release remains verified at 529 S3 objects and 560 public checks; no rollback is required. Existing YouTube/Vimeo/SoundCloud iframe attributes remain immutable.

## Problem and evidence

The returning review browser revalidated the repaired parent data page but reused old embedded child documents. Hospital/city frames still executed their original HTTP Leaflet loaders and failed. Direct child navigation plus reload rendered the repaired headings and tables, while returning to the parent still reused its older iframe cache entry. A CloudFront invalidation does not evict previously stored browser documents.

## Scope and flow

Original 527-object preservation baseline -> same deterministic overlay -> add one stable release-version query parameter to same-site internal iframe URLs -> 529-object follow-up build. External media URLs and attributes, reporting, child documents, data, binaries, and the two shared assets stay unchanged.

Use a configured, documented revision token, preserving any existing query and fragment without duplication. Relative, root-relative, and same-host absolute internal iframe URLs are recognized; external origins are excluded. The validator resolves references by path, so the version parameter cannot conceal a missing child file. Future internal child repairs require bumping the revision.

Expected live delta is only the parent HTML files containing internal frames (data, effects wrappers, and gallery parents). Reject additional changes or deletions. No CloudFront policy, permissions, cache settings, new service, or external-video repair is included.

## Tests and acceptance

1. RED test demonstrates internal iframe URLs have no version token before the fix.
2. GREEN checks add exactly one token, preserve queries/fragments and external iframe attributes, and keep the complete preservation suite passing.
3. Compare the follow-up build against the frozen first release: only declared parent HTML changes, zero additions/deletions; all child file hashes unchanged.
4. Freeze separate build/validation/review hashes; independently review the cache delta and rerun regression tests.
5. Back up all 529 current production objects to a new unique prefix in the requested backup bucket using the existing approved operations tools. Use a separate state directory; retain the first release's state and backup.
6. Fresh pinned-version preflight -> conditional selected parent uploads -> scoped cache invalidation -> all-object/authenticated/public verification.
7. In the same returning browser that demonstrated the stale frames, reload the parent and verify the new internal iframe URLs, repaired chart controls, map headings/tables, and maps without manually reloading each child.

Failure of any preservation or current-source guard stops the follow-up. The first release remains recoverable from its recorded state; the follow-up has its own verified backup and journal. No new user approval is needed for this correction to the already approved cache acceptance requirement.
