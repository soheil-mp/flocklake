# Security policy

## Supported versions

FlockLake is in early development. Security fixes go to the `main` branch and the latest
release only.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report it privately through GitHub:
[Security → Report a vulnerability](https://github.com/soheil-mp/flocklake/security/advisories/new).
Include what you found, how to reproduce it, and the impact you expect.

You can expect an acknowledgement within 7 days and an assessment within 14 days. Once a fix is
released, the advisory is published with credit to you, unless you prefer to stay anonymous.

## Scope

In scope: the code in this repository, its container images, workflows and default
configuration.

Out of scope: the upstream data services FlockLake reads from (Aloft, EUMETNET OPERA, NOAA
NEXRAD, Open-Meteo). Please report problems with those services to their operators.

## How the project protects itself

- No secrets in the repository: gitleaks runs before every commit and over the full history in
  CI; GitHub secret scanning with push protection is enabled.
- Dependencies are locked, updated through grouped Dependabot pull requests with a cooldown, and
  limited to permissive licences.
- GitHub Actions run with no default permissions and are pinned to commit SHAs.
