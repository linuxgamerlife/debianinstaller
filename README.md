# Debian Installer

This exists because I was curious whether you can get something close to the same experience as Arch, but on Debian.

It is 100% vibecoded, but intelligently prompted by me.

This is a proof of concept. One thing I like about Arch is the build-from-nothing aspect, and this project is an attempt to get a similar feel with a Debian base install.

## Current Scope

This is built for VMs only right now so you do not accidentally screw up your actual install.

The current goal is simple:

- start from a Debian live environment in a VM
- run the installer from TTY
- get through the base install, then configure locale, timezone, keyboard, and desktop environment interactively using the native Debian tools
- reboot into your chosen desktop environment

## Prerequisites

Inside the Debian live environment:

```bash
sudo apt install git
```

Then:

```bash
git clone https://github.com/linuxgamerlife/debianinstaller
cd debianinstaller
chmod +x debianinstall.py
sudo ./debianinstall.py --interactive
```

## Usage

Run with `--interactive` to get a menu where you can set:

- target disk (default `/dev/vda`)
- hostname
- username
- package profile (`minimal-tty` or `standard-tty`)
- mode (`plan` to dry-run, `apply` to actually install)
- state file path (for resume support)

Locale, timezone, keyboard layout, and desktop environment are configured interactively mid-install using the standard Debian ncurses tools — you will be prompted for these automatically.

### Modes

**plan** — prints every command that would run without executing anything. Good for checking what will happen first.

**apply** — runs the install. Requires root, a UEFI environment, and a VM (checked automatically).

### Resume

If an install is interrupted, resume from where it left off:

```bash
sudo ./debianinstall.py --resume --mode apply
```

## What Gets Installed

The installer writes DEB822 apt sources covering:

- `trixie`, `trixie-updates`, `trixie-backports`
- `trixie-security`
- `main contrib non-free non-free-firmware`

i386 architecture is enabled by default (required for Steam and 32-bit software).

### Package Profiles

**minimal-tty** — bare minimum: sudo, locales, keyboard-configuration, console-setup, tasksel

**standard-tty** — adds: ca-certificates, curl, wget, less, vim-tiny, network-manager, openssh-server, tasksel

`linux-image-amd64` and `systemd-sysv` are installed on top of whichever profile you pick.

## Interactive Configuration Mid-Install

After packages land, the installer drops you into the standard Debian ncurses configuration screens in order:

1. **locales** — select your locale
2. **tzdata** — select your timezone
3. **keyboard-configuration** — select your keyboard layout
4. **tasksel** — select a desktop environment (or skip for TTY only)

These run inside the chroot so your choices apply to the installed system directly.

After tasksel, the installer automatically detects which display manager was installed (`sddm` for KDE/LXQt, `gdm3` for GNOME, `lightdm` for XFCE/MATE/Cinnamon) and enables it along with `graphical.target`. If you skipped the DE in tasksel the system stays on `multi-user.target`.

## After Install

Once all phases are complete you will be asked:

- **Install latest kernel from backports?** — installs `linux-image-amd64` from `trixie-backports` and runs `apt upgrade`
- **Reboot now?** — reboots out of the live environment

You will come back into whichever desktop environment you selected in tasksel, or a TTY login if you skipped it.

## Notes

Right now this is intentionally narrow:

- VM use only (QEMU/KVM)
- UEFI + GPT + ext4 only
- proof of concept
- focused on the install-from-scratch feel

If you use it, treat it like an experiment and use disposable VMs.
