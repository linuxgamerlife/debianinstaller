# Changelog

## v0.0.5 — 2026-04-06

### Added

- `lsblk` output shown before disk selection in the wizard (both VM and real hardware)
- Immediate disk confirmation after entering disk name — "Use /dev/vda? This will erase all data."
- Screen cleared on first run before banner
- "Almost there!" message before final optional steps
- Boxed banners for backports kernel prompt and reboot prompt explaining what each does

### Changed

- Removed plan/apply mode — installer always runs (apply)
- Descriptive wizard prompts: "What would you like your hostname to be?", "What username would you like to use?", "Which package profile do you want?"
- State file step now explains its purpose: records completed phases so install can resume if interrupted
- State file default renamed from `debianinstall-v1-state.json` to `debianinstall-state.json`
- Summary menu reduced to 5 items (mode removed)

---

## v0.0.4 — 2026-04-06

### Fixed

- Banner shown twice in interactive mode — removed duplicate from wizard, kept in `main()` and on summary screen after clear
- Drive wipe warning and apply confirmation box moved to just before install starts (after password collection), not mid-wizard
- Password prompts changed from "Enter password for" to "Create password for"

### Changed

- Summary screen now shows "Thank you. I have all the info I need to get started." before the summary list
- Wizard exits cleanly on `y` — all destructive confirmations happen separately in the final pre-install step

---

## v0.0.3 — 2026-04-06

### Added

- ASCII banner shown on every run and on the summary screen:
  `LGL Debian Installer v0.0.3 / 100% Vibe Coded / Intelligently Prompted / GitHub URL`
- Step-by-step wizard replaces the old menu — each option presented one at a time with `Step N:` heading
- Summary screen after wizard — clear, banner, "Thank you" message, numbered list, edit by number or `y` to continue
- Drive wipe warning and apply confirmation box now appear just before the install starts (after password collection), not mid-wizard
- Apply confirmation box — shows target drive name, requires typing it exactly to proceed
- Non-VM bypass — if apply mode and no VM detected, shows a warning box, runs `lsblk` so drives are visible, then asks for a second confirmation before allowing install on real hardware

### Fixed

- Banner was shown twice when running interactively — removed duplicate from wizard, kept in main and on summary screen
- Password prompts now say "Create password for" instead of "Enter password for"

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
