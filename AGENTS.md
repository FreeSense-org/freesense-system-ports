# freesense-system-ports agent rules

System-only port definitions (FreeSense-system, FreeSense-upgrade, FreeSense-repoc, ...). Release rules are in
`FreeSense-org/freesense-os-base` `docs/release-policy.md` (R1–R9).

- `main` is Development (1.2). Changes land here first.
- `RELENG_1_1` is the Stable 1.1 maintenance branch. Only fixes reach it, as
  `git cherry-pick -x` of a `main` commit through a pull request against
  `RELENG_1_1`. Never push to it directly, never force-push it.
- `v1.1.N` tags mark released commits; they are created by the Stable seal
  and never moved or deleted.
- Every script fix to a hand-versioned port (FreeSense-upgrade, FreeSense-repoc) bumps its PORTREVISION, or installed systems never receive it.
- Never give FreeSense tools environment variable names that pkg also reads (REPOS_DIR, FETCH_TIMEOUT); see the 1.1.1-1.1.4 updater failure.
- The FreeSense-system pkg-plist must list every `src/` file of `freesense`; CI audits both repositories.
- Merge with `gh pr merge --rebase` (keeps the `dev@freesense.org` author).
