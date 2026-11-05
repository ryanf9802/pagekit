# Security

Please report a vulnerability privately, through
[GitHub's private reporting](https://github.com/ryanf9802/pagekit/security/advisories/new), rather than in a public issue.
Include what you found, how to reproduce it, and what an attacker could do with it.

pagekit is maintained on a best-effort basis. Fixes go to `main`, and `pagekit update` delivers them.

## What pagekit trusts

- **Profiles run commands.** `[checks]`, `[send]`, and `root_command` run what a profile names, so read a profile before
  using it from a repository you do not trust. This is by design, and is [documented](docs/profiles.md#commands-in-profiles).
- **The page server is local.** It serves pages from your machine, and it should never be exposed to the public internet.
  A way for a remote site or another machine to reach it uninvited would be a vulnerability.
