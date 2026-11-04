# Install and run

This English technical reference covers first installation, a standalone synthetic example and the CLI. Use Python **3.10+**. The CSV path and generated runtime use the standard library. XLSX input additionally uses the pinned optional dependencies `openpyxl==3.1.5`, `defusedxml==0.7.1` and `et-xmlfile==2.0.0` in the Python environment that runs the toolkit/app.

## Obtain the source

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
```

The shell examples below target macOS/Linux. `python3` may be named `python` on your machine. PowerShell equivalents are provided for the skill copy.

## Claude Code

Copy the complete skill directory into the personal skill directory. For a fresh installation:

```bash
mkdir -p ~/.claude/skills
cp -R skills/data-to-app ~/.claude/skills/data-to-app
```

If the destination already exists, inspect your existing copy before replacing or merging it, especially if you made local changes. Start a new agent session if the host does not discover the skill immediately.

In Windows PowerShell, from the repository directory:

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse "skills\data-to-app" "$HOME\.claude\skills\data-to-app"
```

## Codex

For a fresh personal installation:

```bash
mkdir -p ~/.agents/skills
cp -R skills/data-to-app ~/.agents/skills/data-to-app
```

PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.agents\skills" | Out-Null
Copy-Item -Recurse "skills\data-to-app" "$HOME\.agents\skills\data-to-app"
```

Respect existing destination files as described above. Then name Data to App in an ordinary task. Host-specific skill discovery, file permissions and available browser/terminal tools still apply.

## Give the agent a job

> Use Data to App on `./exports`. Build a local tool for searching stock, reviewing low-stock items, editing reorder levels and notes, then importing the next export while preserving local work. Launch the app and verify those actions.

The skill should inspect the data, resolve material identity/semantic ambiguities, create the model and app, run it and check the main operations. A plan alone is not the intended result. The bundled toolkit is a starting engine; the agent can extend the generated source for the requested workflow.

## Standalone inventory workspace

From the repository directory:

```bash
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

Open `http://127.0.0.1:8765`. Keep that terminal running. The output directory must be new; generation does not overwrite any existing directory. The app includes runtime source, local assets and its database and can run independently of the installed skill.

## Inspect your files

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
python3 skills/data-to-app/scripts/dta.py inspect ./exports --out ./profile.json
```

Input can be an explicit file or a directory of top-level supported files. Inspect output is machine-readable evidence about columns, values, key candidates and warnings. It does not prove a business identity or infer every relationship.

For XLSX support, use your usual Python environment or a virtual environment:

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

Input is bounded to 10 MiB per file, 50,000 rows per table, 200 columns and 1,000,000 cells. XLSX defaults to the first worksheet and warns when additional sheets exist. The toolkit does not execute spreadsheet formulas. See [the input contract](DATA-CONTRACT.md) for cached-value/format and identity limits.

## Build from a declared model

```bash
python3 skills/data-to-app/scripts/dta.py build ./exports --out ./my-app --manifest ./model.json
python3 my-app/app.py --port 8765
```

The agent normally creates `model.json` after inspecting the files. The manifest declares table IDs, source files, exact columns, explicit keys, editable fields and bounded views. The bundled inventory model at `skills/data-to-app/assets/examples/inventory/model.json` is a concrete example, not a universal model for your data.

## Check a relationship

```bash
python3 skills/data-to-app/scripts/dta.py join-check ./orders.csv ./products.csv --left-key product_sku --right-key sku
```

Review coverage, duplicate keys and projected row multiplication. No business join is performed automatically.

## Preview and apply the next snapshot

In a second terminal, from the repository directory:

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

Apply after reviewing the preview:

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv --apply
```

The app also offers file upload, preview and confirmation. Each import is a complete snapshot of one table. Absent records become missing and remain retained; a partial export therefore marks omitted records missing. Local/source changes that disagree become conflicts for review. Schema changes and ambiguous duplicate keys reject before mutation. See [DATA-CONTRACT.md](DATA-CONTRACT.md).

## Troubleshooting

- **Python not found:** install a supported Python and use the interpreter name available in your shell.
- **XLSX reader missing:** install the pinned XLSX dependencies above into the interpreter environment used for this command/app.
- **Output already exists:** choose a new output directory. Do not rebuild over a workspace containing edits.
- **Port occupied:** stop the other local process or choose another port and use the printed URL.
- **Import rejected:** inspect headers, keys, duplicate rows and schema compatibility. Correct the input/model deliberately rather than weakening identity checks.
- **Stale revision:** refresh the app and review the newer data before submitting again.

The local app is not a public multi-user server. [Privacy and deployment boundaries](PRIVACY.md) explain what local operation does and does not cover.
