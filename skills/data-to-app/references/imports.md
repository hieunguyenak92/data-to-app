# Reimports: source, local and incoming

For each keyed record the store keeps the most recently accepted source row and local overrides separately. The visible value is the source with local overrides applied. An import is a complete snapshot for one table and requires unchanged columns and valid keys.

| Last source | Local override | Incoming | Expected behavior |
| --- | --- | --- | --- |
| 12 | none | 14 | Update visible value to 14. |
| 12 | 20 | 12 | Keep local 20; source did not change. |
| 12 | 20 | 20 | Values converge; remove unnecessary override. |
| 12 | 20 | 14 | Keep local 20; show 12 / 20 / 14 conflict. |

An identical latest snapshot is a no-op, including unresolved conflicts. A conflict does not disappear merely because the user previews or imports the same file again. The review controls explicitly choose local or source. Local means retain the override; source means accept the incoming value. Revision checks prevent an outdated page or preview from overwriting later work.

## Missing and new records

A new key creates a record. A key absent from a complete snapshot is retained as missing, with source/overrides available for review; it is not silently erased. A later snapshot that restores the same key reactivates it. Export contains active effective records by default. This model is unsuitable for partial transaction feeds unless a separate append/event contract is implemented.

## Atomic application

Validate the entire uploaded table before making changes: columns, key fields, empty keys, duplicate-key conflicts and limits. Any failure leaves current rows and revision unchanged. Preview is read-only. Apply requires the revision used for the preview; otherwise make a new preview. The browser stages bounded uploads temporarily in memory, not as permanent arbitrary files.

An exact snapshot is identified from canonical source content; raw-file provenance can differ because of row order or CSV formatting. Do not assume every historical snapshot is always ignored: deliberately importing an older different snapshot can change the latest source state and create conflicts.

## Local edits and export

Only model-declared nonkey fields can be edited. Editing is not permission management for a shared team; the app is a loopback workspace for one local operator. Export uses CSV quoting and spreadsheet-formula guarding by default. Guarding changes an exported representation, not the stored source values. A raw export is a deliberate choice for appropriate downstream tooling, not the default browser download.

Back up the generated app directory, including `.data/`, before replacing/removing the workspace. Source retention and import history are not a claim of arbitrary point-in-time database rollback. Shared deployments, background sync and changing the schema require explicit additional engineering.
