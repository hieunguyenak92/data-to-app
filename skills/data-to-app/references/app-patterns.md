# From work to an operational app

Choose the smallest useful workflow and make it run. Reuse the user's existing project if present. For a standalone workspace the bundled app generator supplies dependable primitives; the agent still chooses semantics and task-specific behavior.

| User job | Likely grain/key | Useful first interface | Decisions to establish |
| --- | --- | --- | --- |
| Inventory attention | `(warehouse, sku)` or a confirmed SKU | Search stock, low-stock view, reorder note/threshold editor, next snapshot | Stock snapshot vs movement log; same unit for threshold; which fields are locally owned. |
| Client follow-up | Stable contact/customer ID; activities separately keyed | Contact search, status/owner/next-action editor, activity table, refreshed export | Email/name may change; activity count must not multiply contacts; source vs local owner of each field. |
| Work tracker | Task ID; project separate | Task search, due/status attention view, permitted status edits, refreshed snapshot | Date semantics/time zone; states allowed; whether the input is a full snapshot. |
| Order exceptions | Line ID, not repeated order ID | Pending/error attention, line detail, allowed operational note, export | Orders vs lines; quantities vs prices; source system owns fulfillment facts unless instructed. |

## Result-oriented interface

Use meaningful titles, natural labels and a short path from finding a record to performing the action. Preserve source column names in the model; display labels can explain them. Avoid invented KPI totals, stock valuations or charts unsupported by semantics. Show known-source/local/missing/conflict states only when they help the user make the next decision.

The bundled UI provides a usable foundation, not a promise to implement every workflow. If the job requires a new action, add it in the generated source, validate its inputs, make it persist and exercise it in the browser. Do not leave a nonfunctional button or say a feature exists because a card is visible.

## Adaptation boundaries

Use the model's declarative view predicates for straightforward attention views. Advanced joins, custom validation, calculated columns or domain actions belong in explicit tested code with recorded assumptions. Keep generic source/local import semantics consistent rather than creating a second ad hoc merge system in the UI.

For multi-user/cloud requests, work within the existing application stack and add real auth/access/deployment support. Do not publish the single-operator local server and call it a secure team app. Do not install a large framework solely to produce a familiar-looking dashboard when a small local app meets the job.

## Completion examples

- Inventory: search `00128`, edit a permitted threshold, apply next snapshot, inspect conflict, resolve, export and confirm the chosen value.
- Contacts: update a local follow-up note, reimport a source that changes the company field, confirm both survive, show missing records retained.
- Tasks: modify status, restart app, verify persistence, import an unchanged snapshot and confirm no extra history/revision change.

Evidence accompanies the functioning object. A profile, a test file or a model document alone is not the finished task.
