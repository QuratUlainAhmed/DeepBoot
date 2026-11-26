# Branch merge tracker

This file records improvement work brought into `main` and local work that is still waiting to be reviewed and merged. Keep source branches after merging so their work remains easy to trace.

## Merged into `main`

| Date | Source | Changes | Result |
| --- | --- | --- | --- |
| 2026-11-26 | `experiment/inference-allocation-controlled` (`5a94a70`) | E01/E02 metadata audit, registry and results updates, follow-up tracking, and comparison edits | Fast-forwarded into `main`; source branch kept |
| 2026-11-26 | `origin/main` (`1aa9849` through `40d0be3`) | Pollux optimization-time investigation and follow-up | Merged into `main`; includes PR merge commit |
| 2026-11-26 | `origin/qurat` (`b3dfe22`) | E02 configuration audit and E08 DeepBoot small-workload rerun | Merged into `main`; source branch kept |
| 2026-11-26 | `origin/experiment/aiss-ablation` (`8aeb595`) | AISS on/off ablation data, analysis, report, and plots | Merged into `main`; source branch kept |
| 2026-11-26 | `origin/experiment/E02-deepboot-afe` (`d589451`) | E02 result branch history | Merged into `main`; result files already matched the consolidated results |
| 2026-11-26 | `origin/experiment/E_04-deepboot-workload-scaling` (`7c754d4`) | E04 workload scaling branch history | Merged into `main`; result files already matched the consolidated results |

## Waiting for review

| Source | Changes | Status |
| --- | --- | --- |
| Local untracked files: `docs/inference_allocation_comparison.md`, `experiment/results/team_experiments/E08_infer_alloc_control/` | Inference allocation controlled experiment results | Not committed to a branch; review and commit before merging. This is separate from the E08 rerun merged from `origin/qurat`. |

## Updating this tracker

When new improvement work is ready:

1. Fetch `origin` and inspect `git status --short --branch`.
2. Compare the candidate branch with `main` using `git log --oneline main..BRANCH` and review its file changes.
3. Merge the candidate into `main`, keeping its source branch.
4. Add a row under **Merged into `main`** with the date, branch and commit, a short change summary, and merge result.
5. Move any completed item from **Waiting for review** to the merged table, then push `main` when requested or authorized.

Do not merge a branch just because it exists: first check whether its unique commits are already in `main` and whether it contains older versions of files that `main` has since updated.
