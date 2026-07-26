# FreeSense System Ports

This repository contains the FreeBSD ports overlay required to build the
FreeSense operating system, update repository, and installation media.

The boundary is intentional:

- System/runtime ports live here.
- Optional packages installed from the FreeSense UI live in
  [`freesense-packages`](https://github.com/FreeSense-org/freesense-packages).
- The upstream FreeBSD ports tree remains an external build input.

Changes here may trigger a new versioned system repository, but never an
optional-package repository rebuild. The product version and package train are
derived from `src/etc/version` in the FreeSense source repository.

`sysutils/FreeSense-cloud-init` is part of the System build closure so its
dependencies come from the pinned FreeBSD ports tree. It is installed only by
the cloud-image assembly stage; installer ISOs and ordinary appliances do not
include or execute the adapter.

Do not add ports named `FreeSense-pkg-*` or the optional-package catalog
framework to this repository. The boundary check in CI enforces that rule.
