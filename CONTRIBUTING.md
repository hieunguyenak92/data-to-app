# Contributing

Start with a real work request and a small synthetic example. Explain what the user should be able to do, the observed behavior and a reproducible command. Avoid sharing customer exports, credentials, private identifiers or generated workspace databases.

## Development

Python 3.10+ and Node.js are used for verification. CSV/runtime require no third-party package; the development environment includes optional XLSX dependencies and Ruff.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
node --check skills/data-to-app/assets/app/app.js
python3 tools/check_docs.py
```

On Windows use `.venv\Scripts\python` / `.venv\Scripts\ruff`. Socket integration tests bind to loopback; an environment that blocks sockets needs a suitable local test permission, not skipped behavioral claims.

Keep source/local/incoming semantics, key identity and atomic import guarantees intact. Add a regression for a substantive behavior change. Use explicit source/version assumptions for XLSX and never evaluate workbook formulas as executable code.

Skill changes should be tried on the inventory example and another domain. Evaluate the functioning app and next import; an instruction-format test alone does not establish value. Record failures and verification limits. README copy and all nine localizations must stay consistent with shipped behavior. Native-speaker corrections are welcome; do not claim that review before it occurs.

Keep the installed skill self-contained. Runtime code belongs in `skills/data-to-app/scripts/data_to_app/`; canonical examples live under the skill's assets so installed first-run examples still work. Generated apps and private data do not belong in commits.
