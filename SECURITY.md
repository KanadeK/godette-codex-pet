# Security policy

## Supported versions

Security fixes are provided for the latest tagged release.

## Reporting

Do not open a public issue for a path traversal, unsafe archive, destructive
installer, or secret-exposure problem. Use GitHub's private vulnerability
reporting for this repository.

Include the affected command, platform, release version, minimal reproduction,
and whether any target or backup was changed. Do not attach real Codex session
content.

## Security model

- The project has no telemetry or analytics.
- Trace fixtures never require prompt, message, path, account, or tool payload
  content.
- Archive extraction rejects absolute paths, parent traversal, symlinks,
  cross-platform name collisions, unsafe Windows names, and oversized archives.
- Installation validates source and stage before replacement.
- Existing packages are moved to recoverable backups.
- PetDiff reads only the two named pet packages and writes only to its named
  output directory.

The project does not claim to sandbox Pillow decoders. Compare and install
packages from trusted sources, and keep Pillow updated within the supported
version range.
