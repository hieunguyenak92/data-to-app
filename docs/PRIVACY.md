# Privacy and local runtime

This English reference separates the generated application's behavior from the AI host used to create it.

## Generated application

The core generated app uses a local Python HTTP server, SQLite database and local HTML/CSS/JavaScript assets. Its server binds to `127.0.0.1`. The core import, search, edit, conflict and export operations do not require a hosted service or paid AI API.

The local server is designed for an individual workspace. It validates loopback request context and uses a per-runtime token for mutation requests. Those controls do not provide multi-user authentication. Do not expose it to the internet or treat it as a shared cloud service without designing and verifying that deployment separately.

## Data locations

Generated workspaces can contain copies of input data, a SQLite database, source/local/incoming conflict values and import history. CSV exports contain effective record values. These files can be sensitive even when the app itself runs locally.

Keep workspaces and backups in an appropriate location. Review files before committing a generated app or publishing an export. Use synthetic data in public issues and demonstrations. Deleting an export does not automatically delete its source data or database history.

## AI host

While the skill builds or modifies an app, Claude, Codex or another host may read files and send content to its model/provider according to that host's settings and policies. Installing this skill does not change those policies or create a guarantee that the entire authoring process stays on the device.

Only provide data the agent is allowed to access. Credentials, external service connections and cloud deployment are separate capabilities; the core local app does not need them.

## Extensions

An agent or developer can extend the generated source with additional services or model-powered features. Such changes can alter data flow and runtime requirements. Review those changes before relying on the core application's local-runtime description.

## Limits

This project does not promise anonymization, encryption at rest, regulatory compliance, complete deletion across backups or security certification. The intended first use is an individual local workspace with supplied data and a bounded workflow. Report suspected security problems using the repository's security guidance when available.
