# HookedAZ local browser acceptance

Checked November 5, 2026 against the preservation build served at `http://127.0.0.1:8765/`, using the in-app browser and CUA. Tested at 320 × 740 and 1280 × 900 CSS pixels. Temporary viewport override was reset.

## Verified behavior

- Homepage: no page-level horizontal overflow at 320px (320px viewport and scroll width). Archive notice is readable; hero title and subtitle have opaque light surfaces and dark text, with no notice/title overlap. First Tab reaches the skip link; Enter moves focus to `archive-main`.
- Mobile menu: opens with expanded state, all long labels wrap visibly, Escape closes it and returns focus to `static-toggle`, and the closed panel disappears from the accessibility tree. About actually navigates to `/about/`.
- Data navigation: the mobile Explore more data button responds to Enter and exposes expanded state. Every map tab renders its named map and controls after switching from a hidden panel. Right Arrow changes the selected hospital tab to cities. The years chart renders; Enter on the gender control changes selected state and shows Male/Female series.
- Data alternatives: native details opens the cities table and the race/gender table. Original years/counts are visible, including 2013 total 561. County suppression labels are covered by the independent source-data validator.
- Maps: county overlay and legend render; Maricopa and Pima ZIP views, hospital and city maps render. Local point symbols replace missing marker images. Direct hospital zoom changes the view; selecting Kingman opens the original `Overdose cases:20` popup. Fullscreen enters and exits through the map control. UTF-8 declaration fixes the direct hospital heading to `2009–2013`.
- Feedback: the old URL remains readable and clearly says submissions are closed; no response fields render.
- Resource guide: historical organization names/contact information remain, with adjacent unavailable/parked notices replacing failed outbound actions.
- Gallery: the original 14-photo heroin-love gallery renders; its native details alternative opens the caption-derived image/caption list.
- Effects animation: original animation renders, and the Animation text disclosure exposes its preserved text. The builder places that alternative beside the iframe inside main content.
- History page: missing original interactive is replaced by an explicit unavailable notice while its credit and description remain.

## Defects caught and corrected before release

Browser checks caught a pre-existing unclosed homepage script swallowing the new controller, the notice overlapping the hero heading, the new semantic h1 inheriting light low-contrast text, the non-keyboard mobile data disclosure, absent original marker PNGs, and missing UTF-8 declarations in standalone maps. Each was returned to the coder and regression coverage added. Relevant behavior was retested above.

## Limits

This is a targeted acceptance pass, not a WCAG certification. Actual screen-reader speech, genuine browser 200% zoom, OS forced-colors behavior, every photo slide, every popup, and full third-party media playback were not tested. YouTube/Vimeo/SoundCloud addresses and existing attributes are preserved by automated comparisons. Third-party playback differences on localhost are not evidence of new production media changes. Some URL-less MutationObserver errors appeared in the browser environment; they were not attributed to site code. Screenshots were inspected through CUA but not saved as local exports.
