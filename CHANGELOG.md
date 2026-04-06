# Changelog

## v0.0.3 — 2026-04-06

### Added

- ASCII banner shown on every run and on the summary screen:
  `LGL Debian Installer v0.0.3 / 100% Vibe Coded / Intelligently Prompted / GitHub URL`
- Step-by-step wizard replaces the old menu — each option presented one at a time with `Step N:` heading
- Summary screen after wizard — clear, banner, numbered list, edit by number or `y` to continue
- Apply confirmation box — shows target drive name, requires typing it exactly to proceed
- Non-VM bypass — if apply mode and no VM detected, shows a warning box, runs `lsblk` so drives are visible, then asks for a second confirmation before allowing install on real hardware

---

## v0.0.2 — 2026-04-06

### Added

- Automatic display manager detection after tasksel — enables `sddm`, `gdm3`, or `lightdm` and sets `graphical.target` based on what was installed
- Post-install prompt to install the latest kernel from `trixie-backports`
- Post-install reboot prompt

### Fixed

- `graphical.target` was being overwritten back to `multi-user.target` by `configure_system` running after `interactive-config` — `setup_graphical_target` now runs at the end of `configure_system` and always wins

---

## v0.0.1 — 2026-04-05

Initial release.

### Added

- Single-file debootstrap-based Debian installer (`debianinstall.py`)
- Interactive pre-install menu: disk, hostname, username, package profile, mode, state file
- Two package profiles: `minimal-tty` and `standard-tty`
- Phase-based install pipeline with state file and resume support
- UEFI + GPT partitioning (EFI partition + ext4 root)
- DEB822 apt sources: `trixie`, `trixie-updates`, `trixie-backports`, `trixie-security`, with `main contrib non-free non-free-firmware`
- i386 architecture enabled by default (for Steam and 32-bit software)
- Interactive mid-install configuration via Debian ncurses tools: `dpkg-reconfigure locales`, `dpkg-reconfigure tzdata`, `dpkg-reconfigure keyboard-configuration`, `tasksel`
- `tasksel` included in all package profiles for desktop environment selection mid-install
- GRUB EFI bootloader install
- Plan mode (dry-run) and apply mode
- VM-only safety check (blocks apply mode on non-VM hosts)
- Optional command log via `--log-file`
