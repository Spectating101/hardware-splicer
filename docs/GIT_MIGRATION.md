# Git Migration Notes

Hardware-Splicer is the canonical top-level repository for the combined hardware engine.

The old standalone `project_portfolio/Circuit-AI` repository is imported into this repo under `apps/circuit-ai` as subtree history. The current canonical `apps/circuit-ai` worktree is then overlaid and committed on top, so current local work is preserved without keeping a nested `.git` directory.

Nested app `.git` directories are kept only as local migration backups under `.git-migration-backups/`, which is intentionally ignored.
