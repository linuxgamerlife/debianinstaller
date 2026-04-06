# LGL Debian Installer v0.0.8

This exists because I was curious whether you can get something close to the same experience as Arch, but on Debian.

It is 100% vibecoded, but intelligently prompted by me.

This is a proof of concept. One thing I like about Arch is the build-from-nothing aspect, and this project is an attempt to get a similar feel with a Debian base install.

## Current Scope

This is NO LONGER just built for VMs only, so you CAN accidentally screw up your actual install if you are not careful!

The current goal is simple:

- start from a Debian live environment (Recommended)in a VM
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

## Banner

Every run starts with:

```
-----------------------------------------------------
|            LGL Debian Installer v0.0.8            |
|                  100% Vibe Coded                  |
|               Intelligently Prompted              |
| https://github.com/linuxgamerlife/debianinstaller |
-----------------------------------------------------
```

## Usage

Run with `--interactive` to launch the step-by-step wizard:

```
Step 1: Select disk
  (lsblk shown here)
  Disk [/dev/vda]:
  Use /dev/vda? This will erase all data on it. [y/N]:

Step 2: What would you like your hostname to be?
Step 3: What username would you like to use?
Step 4: Which package profile do you want?
Step 5: State file (saves progress for resume if interrupted)
```

After completing the steps, the screen clears and shows a summary:

```
1. disk:            /dev/vda
2. hostname:        debian-vm
3. username:        debian
4. package profile: standard-tty
5. state file:      /var/tmp/debianinstall-state.json

Select number to change, or y to continue:
```

Select a number to change that item, or `y` to proceed. After confirming, you will be prompted to create passwords, then shown a final drive wipe warning before anything destructive runs.

Locale, timezone, keyboard layout, and desktop environment are configured interactively mid-install using the standard Debian ncurses tools — you will be prompted for these automatically.

### Non-VM installs

If no VM is detected, the installer shows a warning and runs `lsblk` so you can see your drives before deciding. You will be asked to confirm twice. Use with care.

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

The following firmware packages are installed before the kernel on every install, so firmware is baked into the initramfs:

- `firmware-linux` / `firmware-linux-nonfree` — general Linux firmware
- `firmware-amd-graphics` — AMD GPU firmware, required for SDDM/Xorg to start on AMD hardware
- `firmware-misc-nonfree` — covers a wide range of USB devices, webcams, and controllers

This prevents boot issues with USB controllers, AMD GPUs, and other devices that require firmware to initialise.

## Interactive Configuration Mid-Install

After packages land, the installer drops you into the standard Debian ncurses configuration screens in order:

1. **tzdata** — select your timezone
2. **keyboard-configuration** — select your keyboard layout
3. **tasksel** — select a desktop environment (or skip for TTY only)

These run inside the chroot so your choices apply to the installed system directly.

After tasksel, the installer automatically detects which display manager was installed (`sddm` for KDE/LXQt, `gdm3` for GNOME, `lightdm` for XFCE/MATE/Cinnamon) and enables it along with `graphical.target`. If you skipped the DE in tasksel the system stays on `multi-user.target`.

## If You End Up at a TTY After Reboot

It is easy to miss selecting a desktop environment in tasksel — you need to press **Space** to select it, not Enter. If you reboot into a TTY, run:

```bash
sudo tasksel
```

Use the arrow keys to highlight your DE and press **Space** to select it (you should see an asterisk `*` appear), then press **Enter** to install.

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
