ROLLOUT RESULT CORRECTION

The previous batch script mislabeled scheduled snapshot skips as FAILED because main.py returned exit code 2. This version distinguishes IMPORTED, SKIPPED_NOT_DUE, FAILED and preserves all existing collector/data behavior.

IMPORTANT: DO NOT use this corrected release to replace your working data folder.
If you already completed the earlier rollout, your data is preserved in the original v07_integrated_candidate folder. This release contains the corrected rollout logic, but rerunning it in a fresh folder would create another database copy. For the already-completed rollout, its four logs prove routine skips; no reimport is necessary.

Original v0.6 stays intact.
