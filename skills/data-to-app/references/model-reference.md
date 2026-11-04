# Model version 1

The agent writes this JSON; the user gives the ordinary work request. The model is data, not executable code. A minimal example:

```json
{
  "version": 1,
  "title": "Client workspace",
  "tables": [{
    "id": "contacts",
    "label": "Contacts",
    "source": "contacts.csv",
    "key": ["contact_id"],
    "columns": ["contact_id", "name", "status", "next_action"],
    "editable": ["status", "next_action"],
    "views": [{
      "id": "follow-up",
      "label": "Needs follow-up",
      "rule": {"left": "status", "op": "eq", "value": "follow-up", "type": "text"}
    }]
  }]
}
```

- `version`: exactly 1.
- `title`: user-facing app name.
- `tables`: one or more independently keyed source tables.
- `id`: lowercase letters, digits, `_` or `-`, starts with a letter, at most 64 characters.
- `label`: human table name.
- `source`: relative source path inside the input directory; defaults to `<id>.csv`. Sources outside that directory and symlinks are rejected. One explicit input file can supply a single table.
- `sheet`: optional worksheet name for XLSX. An omitted worksheet uses the reader's documented default.
- `columns`: source headers in their original order. Build can fill this list from the reader if omitted; declare it explicitly for reviewable models. Subsequent snapshots must use the same schema.
- `key`: a nonempty list of stable identity columns. Key fields cannot be editable.
- `editable`: nonkey columns the user may change in the local workspace. An empty list makes that table read-only apart from import.
- `views`: optional named attention filters. Each rule uses `left` as a column, `op` as a supported comparison, and either `right_field` or a literal `value`. Types are `text` or `decimal`; invalid/nonfinite decimals do not match. There is no eval language.

The bundled inventory example demonstrates a decimal field-to-field comparison (`stock < reorder_level`) and a text literal comparison (`status == pending`). Use tested supported operators and simple rules; extend custom business behavior in generated source when necessary.

```sh
python3 <skill>/scripts/dta.py build ./exports --out ./client-app --manifest ./model.json
python3 ./client-app/app.py --port 8765
```

Output directories are new and are not overwritten. Retain the entire generated workspace for persistence and backups. A model edit after generation does not itself migrate stored data; changing schemas requires explicit engineering rather than bypassing the import checks.
