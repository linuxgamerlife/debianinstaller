# Changelog

## v0.1.0 — 2026-04-11 ⚠️ UNTESTED

### Changed

- **New direction** — installer is now focused on Niri + Noctalia as the desktop stack, with TTY-only as the alternative. tasksel is gone from the install flow.
- Replaced tasksel DE selection with a dedicated **desktop** wizard step (step 11): `none` (TTY) or `niri-noctalia`
- Removed `tasksel` from all package profiles
- When `niri-noctalia` is selected:
  - Noctalia apt repo added to sources (GPG key fetched on host before chroot)
  - `noctalia-shell`, `greetd` installed via apt
  - Runtime deps: `libgl1-mesa-dri`, `xwayland`
  - Default config utilities: `alacritty`, `fuzzel`
  - Desktop integration: `xdg-desktop-portal-gtk`, `swayidle`
  - `niri` and `xwayland-satellite` built from source (not packaged in Debian Trixie); new `build-from-source` phase handles this with all required build deps installed first
  - Banner displayed before source builds explaining compilation time and internet dependency
  - greetd configured to autologin the created user with `niri-session`
  - `graphical.target` set as default
- When `none` is selected: `multi-user.target` set, no display stack installed
- `curl` and `gnupg` added to live prerequisites (required to fetch the Noctalia GPG key on the host)
- README updated to reflect new direction; added post-install instructions for installing other DEs manually (minimal) or via tasksel (more complete)

---

## v0.0.9 — 2026-04-06 ⚠️ UNTESTED

### Added

- **Filesystem selection** — ext4 (default), btrfs (with `@`/`@home` subvolumes, zstd compression, noatime), xfs
- **Swap** — none, swapfile, or dedicated partition; size configurable
- **Separate /home partition** — optional, root size prompted with disk size hint, rest of disk goes to home
- **Audio selection** — pipewire (default, includes wireplumber + pipewire-pulse), pulseaudio, or none
- **Network backend selection** — NetworkManager (default) or systemd-networkd (with auto wired DHCP config)
- Wizard expanded to 10 steps; summary menu updated to show all 10 options
- Live prerequisites auto-install `btrfs-progs` or `xfsprogs` based on selected filesystem
- btrfs/xfs tools installed inside chroot via package profile
- Cleanup now unmounts `/home` before root
- Clear screen after each ncurses configuration section (tzdata, keyboard, tasksel)

### Fixed

- btrfs swapfile: `chattr +C` applied before `fallocate` to disable copy-on-write — required for swap to activate on btrfs
- Root partition size no longer defaults to `50G` — disk size shown as hint, user must enter value explicitly

---

## v0.0.8 — 2026-04-06

### Added

- `firmware-amd-graphics` added to firmware install step — required for SDDM/Xorg to start on AMD hardware
- `firmware-misc-nonfree` added to firmware install step — covers USB devices, webcams, and controllers

### Fixed

- CUPS masking changed from `disable` to `mask` — `disable` was not surviving into the installed system; `mask` (symlink to `/dev/null`) is more forceful and persists across reboots

---

## v0.0.7 — 2026-04-06

### Added

- `firmware-linux` and `firmware-linux-nonfree` installed before the kernel on every install — ensures firmware is baked into initramfs, preventing USB and hardware boot failures on real hardware
- CUPS and cups-browsed disabled automatically after install — prevents boot hang when no printer is present

---

## v0.0.6 — 2026-04-06

### Changed

- Removed `dpkg-reconfigure locales` from interactive install step — locale setup was silently failing inside the chroot, leaving all locale variables unset
- `en_US.UTF-8` is now set silently during `configure_system` — reliable, no user interaction needed
- Users can still change locale post-install with `sudo dpkg-reconfigure locales`

---

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
