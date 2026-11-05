# Live browser acceptance

Verified November 5, 2026 through CUA in the in-app browser at the public HTTPS origin.

The repaired homepage rendered its archive notice, topic heading, dark text on opaque light surfaces, and the preserved external documentary embed. At 320 CSS pixels, the menu opened with expanded state, long labels wrapped, and selecting About navigated to `/about/`. The feedback page displayed closed-submission text and had zero input, textarea or select controls.

The initial live pass identified a returning-browser cache problem: corrected parent HTML still embedded old cached child documents. Direct child URL reloads served repaired bytes, while the same parent's frames retained the old source. This was corrected by the independently reviewed internal-frame revision change.

After the follow-up invalidation completed, the **same browser and data-page tab** reloaded only the parent. All six iframe URLs now carried `archive=20261105-r2`. The chart immediately exposed native race/gender controls and its table alternative. Selecting Counties, Maricopa ZIP codes, Pima ZIP codes, Hospitals and Cities exposed the repaired named map and table alternative for every tab; screenshots confirmed map tiles and overlays rendered. No manual child reload was used for this acceptance pass.

The public effects page exposed Animation text and its versioned iframe; the couple's story loaded the versioned heroin-love gallery and Photo descriptions alternative. Temporary viewport overrides were reset.

Authenticated final checks independently passed for all 529 objects. Public verification passed 560 file/directory/404 requests, and all nine distinct versioned embed URLs matched their reviewed child bytes. Local detailed popup/zoom/fullscreen/keyboard evidence remains in `browser-qa.md`. Screenshots were inspected through CUA, without saved screenshot exports. Full screen-reader, OS accessibility-mode, genuine 200% zoom, and complete external-media playback tests were outside this targeted acceptance pass.
