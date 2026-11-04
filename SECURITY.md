# Security and privacy reports

Report a vulnerability privately through the repository's GitHub security advisory feature if it is enabled. Otherwise open a minimal issue asking for a private reporting channel without publishing exploit details or private data.

Include the affected version, a synthetic reproduction, expected/observed behavior and relevant environment. Do not attach customer spreadsheets, credentials or generated databases.

The generated server is a single-operator loopback application. It is not an authenticated shared service. Do not expose it to a network as a production team app. Source values are rendered as text; POSTs require a local runtime token and valid host/origin. These controls are bounded local protections, not a complete security certification.

XLSX import uses bounded ZIP/XML checks and optional dependencies; formulas are read only when cached results exist, with warnings. Export guards spreadsheet-formula prefixes; raw data/backups can still contain sensitive or spreadsheet-active values. See [privacy](docs/PRIVACY.md) and [data contract](docs/DATA-CONTRACT.md).
