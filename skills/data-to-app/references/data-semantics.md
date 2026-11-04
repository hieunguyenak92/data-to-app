# Data semantics: preserve the meaning before building the interface

## Record grain

Describe one row in ordinary language. An order is not an order line; a stock count is not a shipment; a contact is not an activity. A header named `amount` does not identify the unit or whether it is a cumulative total. Recognize exports that repeat a parent-level quantity on every child row. Never sum those repeated values by accident.

Profile observations narrow the questions; they cannot establish business facts. If a timestamp could mean created, fulfilled or last modified, do not silently select one for a business metric. A missing value is not automatically zero, and an absent row is not automatically a request to destroy data.

## Identity

Use an explicit stable key, possibly composite. Distinguish identity from a field that happens to be unique in this small sample. Names/emails can change or collide. A line-item dataset may need `line_id`, not `order_id`; a stock table may require `(warehouse, sku)`.

Preserve exact strings. `00127`, `127`, `A-127` and `a-127` are distinct unless the user supplies a normalization rule. Whitespace and case normalization can merge identities; perform it only as an explicit transformation with collision checks. Key values stay read-only in the generated UI.

Identical duplicate rows can be collapsed and counted. Different records sharing one declared key block the import atomically. Do not pick the first row, the newest-looking timestamp or a favorite value without a policy.

## Relationships and safe quantities

Run `join-check` before creating a related metric. Inspect right-side uniqueness, coverage/unmatched keys and projected row multiplication. A valid many-to-one relationship preserves left grain; a one-to-many expansion needs an intentional new grain; a many-to-many match needs an explicit bridge or aggregation rule.

Keep independently keyed source tables independently visible until a relationship has been established. Do not add quantities simply because both tables expose `sku`. Inventory on hand, pending order quantities and fulfilled order quantities have different meanings. A low-stock comparison can use two quantities in the same confirmed unit; a mixed-currency total requires a currency policy and rates.

Use Decimal for decimal comparisons or money-like exact arithmetic. Exclude nonfinite/invalid values from calculations with visible handling; do not fill them with plausible numbers. Do not infer financial projections, causal conclusions or statistical significance from a small CSV.

## Spreadsheet boundaries

CSV preserves source text. XLSX can store typed numbers with display formats or formula caches. Check the reader's warnings; a formatted identifier must not silently become a quantity. Formula results are not calculated by this toolkit, and a stale or absent cache is not a value the model should manufacture.

The supported input reader is bounded; workbook macros, arbitrary formulas, merged-layout interpretation and external connections are not an app data model. When an export contains such structures, request a flat values export or create an explicit extraction with appropriate tools and explain what was preserved.

## Practical decision notes

Keep a concise note beside the model: one-row meaning, stable identity, permitted edits, source snapshot policy, confirmed units and relationships, unresolved rules. This is agent continuity, not a document the user must author before using the skill. The user receives the app and the useful workflow first.
