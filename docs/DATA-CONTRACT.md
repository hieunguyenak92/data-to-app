# Data contract

This English technical reference describes the model behind the generated local application. The installed skill supplies judgment about the user's job; the deterministic toolkit supplies parsing, profiling, identity, merge and storage operations. A profile is evidence, not a declaration of business meaning.

## Input and values

- CSV input is a text table with a header. The reader checks headers, row shape, encoding/delimiter handling and configured bounds. Symlink inputs and unsupported formats are rejected.
- XLSX input uses the pinned optional dependencies listed in [INSTALL.md](INSTALL.md). The first worksheet is read by default; additional worksheets produce a warning. Formula execution is unsupported. Cached values, missing caches and spreadsheet formatting can affect what is available; ambiguous or unsupported cases must be surfaced rather than invented.
- Source values are stored as strings. The toolkit preserves identifiers such as `00123`; it does not silently convert them to numbers. A profile can suggest a numerical/date/boolean interpretation without changing the original value.
- The input file is a source snapshot. The generated workspace contains a local copy of its data; changes in the original file do not appear until another import is applied.

Input bounds are 10 MiB per file, 50,000 rows per table, 200 columns and 1,000,000 cells. These are parser bounds, not performance benchmarks.

## Tables and identity

A manifest declares each table's ID, label, exact column names, key columns, editable fields and bounded views. Keys may contain multiple columns. Key fields are not editable through the app.

The record identity is a deterministic hash of the exact key strings. Empty keys reject the import. Identical duplicate rows may collapse with an explicit count; differing rows with the same key reject the entire import. Whitespace, case and identifier normalization are business decisions, not automatic merge rules.

Candidate-key profiling checks observed uniqueness/completeness. Uniqueness in one file does not prove that a name, email address or row number is a durable identity. The agent should ask for a material missing identity rule before creating an editable recurring workspace.

## Relationships and grain

The join probe checks key cardinality, coverage, unmatched values and projected left-join row count. Repeated right-side keys can multiply left-side rows and aggregate totals. The probe reports that risk; it does not automatically join tables or infer which measure is valid.

Before deriving a metric, establish what one row represents and which units/time periods the fields use. An order total repeated on every order line cannot be summed as if each line were a separate order.

## Three-way field reconciliation

The store separates the last source row from local overrides. During the next import it compares **base source**, **local override** and **incoming source**.

| Situation | Result |
| --- | --- |
| No local override | Accept the incoming source value. |
| Incoming source equals the prior source | Preserve the local override. |
| Incoming source equals the local override | Values have converged; clear the redundant override. |
| Source and local changed differently | Preserve the local value and expose a conflict with base/local/incoming evidence. |

Choosing `source` resolves a conflict using the incoming value. Choosing `local` keeps the override. Repeating an unchanged latest snapshot is a no-op and does not hide unresolved conflicts. An imported field that was not edited locally can update normally.

## Snapshot imports

An import is a **complete snapshot of a single table**, not an append-only event batch. Records absent from the new snapshot become `missing` and remain stored for review/history. Reappearing keys reactivate. Omitting rows from a partial file therefore marks them missing.

Preview does not mutate records. Apply validates the snapshot and commits atomically. Schema changes, missing/ambiguous keys and differing duplicate keys reject before mutation. A global revision prevents a stale editor, import preview or conflict action from silently overwriting a newer state; the HTTP API returns `409` for a stale write.

## Views and editing

The manifest explicitly grants editable non-key fields. Views use bounded predicates, not arbitrary evaluated expressions or user-provided SQL. A generated starter app can be extended by the agent for the user's task, but extensions need their own behavior checks and must preserve these import/identity rules.

The initial inventory example uses a decimal comparison of stock and reorder level for its low-stock view. The example is synthetic; it is not inventory advice or a complete ERP system.

## CSV exports

The app exports effective values of active records, including local edits. Standard CSV quoting preserves separators and newlines. Spreadsheet-formula guarding is enabled for app downloads and may prefix an apostrophe to cells that spreadsheet software could interpret as formulas. This changes the exported representation, not internal source values.

The engine's explicit raw export mode is for callers who understand that behavior. It must not be presented as a way to execute spreadsheet formulas. Missing-record inclusion is a separate explicit engine option; the app's ordinary download contains active records.

## Scope

The runtime is an individual local workspace. It is not a multi-user authorization system or a database migration platform. Source snapshots, overrides and history are useful evidence, but they are not a universal rollback/recovery guarantee. Back up important generated workspaces and verify important outputs.
