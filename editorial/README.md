# Comintel publication proof

The Radar collection and DeepSeek review produce internal candidates. For a new public feed, review each row against the exact source and record the approval in `editorial/publication-proof.json`. Use the public row ID as the JSON object key. Each entry contains:

| Field | Value |
| --- | --- |
| `record_sha256` | `website.validate_public_feed.record_digest(row)` over the final public record |
| `publisher` | Name of the source publisher |
| `capture_file`, `capture_sha256` | Relative path under `captures/` and SHA-256 of the exact source evidence |
| `captured_at`, `approved_at` | ISO 8601 timestamps with an offset |
| `reviewer` | Editor who compared the row with the source and cleared reuse |
| `reviewed_claims` | Source URL, stable source ID, address, scope, date, date basis, stage, buyer and open supplier package status, using the feed's field names |
| `stage_as_of` | Date on which the source supports the stated stage |
| `rights_basis`, `rights_url` | Dataset or publisher terms supporting the use |
| `independent_source_url` or `verification_limitation` | Corroboration or the specific uncertainty readers should understand |

Keep uncleared evidence and candidates in the internal watchlist. Commit only captures cleared for inclusion in this public repository. Pages deploys only the website assets and public feed. The validator checks consistency and file integrity. The editor is responsible for checking what the source actually says and whether its reuse is permitted. The collector never authorizes public release.

Run `python website/validate_public_feed.py` to check a proposed release. The exact existing November 22 feed is supported for redeployment. Any changed nonempty feed requires record-specific proof. The 15–20 target is editorial guidance and an issue may contain fewer qualifying records.
