# Archive status

This directory preserves the finalized N02 formal-run evidence, source, model checkpoints, SQLite work-call database, and result reports.

The authorization body at `final-formal-run-evidence/authorization.json` is intentionally not published. Its validation and consumption receipts, the frozen authorization contract, and the original checksum entry are retained. The original checksum list describes the complete source tree, so its authorization hash cannot be rechecked from this archive.

The submission lock files, deployment transport ZIP, Python bytecode, and cache directories are excluded. Model checkpoints and `work-calls.sqlite3` are included.
