# Project Memory

Date: 2026-04-06

## Purpose

Proof of concept for getting something closer to the Arch "build from nothing" feeling, but on Debian. VM-first, experimental, single-file installer.

## Active path

`debianinstall.py` only. The `debianinstall/` multi-file package directory is no longer being developed.

## Current install flow

1. Boot Debian live ISO in a disposable VM
2. `sudo apt install git`, clone repo, run `sudo ./debianinstall.py --interactive`
3. Set disk, hostname, username, package profile, mode in the pre-install menu
4. Installer partitions, formats, bootstraps, writes DEB822 sources, installs packages
5. Mid-install interactive screens: locales → tzdata → keyboard → tasksel (DE selection)
6. Installer detects which display manager landed and enables it + sets graphical.target
7. Prompted: install backports kernel? then reboot?
8. Reboot into chosen DE (or TTY if tasksel was skipped)

## Current assumptions

- VM use only (QEMU/KVM)
- UEFI + GPT + ext4 only
- Single whole-disk workflow
- i386 always enabled (Steam)
- trixie is the target release

## Bug fixes applied

- `graphical.target` fix: `interactive-config` set graphical.target but `system-config` ran after and overwrote it with `multi-user.target`. Fixed by moving `setup_graphical_target` to the end of `configure_system` so it always runs last.
- Double banner fix: banner was printed in both `main()` and `run_interactive_setup()`. Removed from wizard.
- Drive wipe warning moved out of wizard into `main()` just before `run()` — fires after password collection, truly last step before destructive changes.
- Plan/apply mode removed — installer always executes. `mode` field kept in Config with default `'apply'` for state file compatibility.
- lsblk shown before disk selection in wizard (always, VM and real hardware).
- Backports kernel and reboot prompts now show boxed banners explaining what they do.
- Locale: dpkg-reconfigure locales removed from interactive step (silently failed in chroot). en_US.UTF-8 now set silently in configure_system. User can change post-install with sudo dpkg-reconfigure locales.

## Known issues and history

- Password leak bug fixed: root/user password commands are redacted in logs and output
- Cleanup issue fixed: `/mnt/dev/pts` lazy unmount before `/dev` recursive unmount
- live-environment prerequisites (`debootstrap`, `dosfstools`, `grub-efi-amd64`) installed automatically in apply mode
- locale/timezone/keyboard removed from pre-install menu — handled interactively mid-install via debconf
- README previously referred to wrong filename (`debianinstaller.py`) — now fixed to `debianinstall.py`

## Unresolved

- End-to-end VM validation not done after v0.0.2 changes
- Disk partitioning is scripted/automated — no interactive partition tool yet (cfdisk noted as candidate for future)
