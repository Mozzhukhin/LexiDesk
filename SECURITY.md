# Security

## Supported version

Security fixes are applied to the latest release and the `main` branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository rather
than opening a public issue. Include the affected version, operating system,
reproduction steps, and the expected impact. Do not include personal vocabulary
databases or other private user data.

LexiDesk does not need network access at runtime. Unexpected outbound traffic,
unsafe parsing of imported files, command injection through the Plasma bridge,
and access outside the documented local data directories should be treated as
security issues.

Dependencies are audited in CI. Release downloads include SHA-256 checksums.
