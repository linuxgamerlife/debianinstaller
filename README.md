# LGL Debian Installer v0.1.0

> ## ⚠️ WARNING — UNTESTED
> **v0.1.0 has NOT been tested end-to-end. Do NOT use on any machine you care about until this warning is removed.**

This exists because I was curious whether you can get something close to the same experience as Arch, but on Debian.

It is 100% vibecoded, but intelligently prompted by me.

This is a proof of concept. One thing I like about Arch is the build-from-nothing aspect, and this project is an attempt to get a similar feel with a Debian base — now with a clear focus on the **Niri + Noctalia** desktop stack.

## Current Scope

This is NO LONGER just built for VMs only, so you CAN accidentally screw up your actual install if you are not careful!

The installer targets two outcomes:

- **Niri + Noctalia** — Niri Wayland compositor with the Noctalia shell. Installed via the Noctalia apt repo, started automatically via greetd on login.
- **TTY only** — base Debian system, no desktop. Log in at a TTY and take it from there.

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
|            LGL Debian Installer v0.1.0            |
|                  100% Vibe Coded                  |
|               Intelligently Prompted              |
| https://github.com/linuxgamerlife/debianinstaller |
-----------------------------------------------------
```

## Usage

Run with `--interactive` to launch the step-by-step wizard:

```
Step 1:  Select disk
Step 2:  Hostname
Step 3:  Username
Step 4:  Package profile
Step 5:  State file
Step 6:  Filesystem
Step 7:  Swap
Step 8:  Separate /home partition?
Step 9:  Audio
Step 10: Network backend
Step 11: Desktop environment
```

After completing the steps, the screen clears and shows a summary:

```
 1. disk:             /dev/vda
 2. hostname:         debian-vm
 3. username:         debian
 4. package profile:  standard-tty
 5. state file:       /var/tmp/debianinstall-state.json
 6. filesystem:       ext4
 7. swap:             swapfile (2G)
 8. separate /home:   no
 9. audio:            pipewire
10. network backend:  networkmanager
11. desktop:          niri-noctalia

Select number to change, or y to continue:
```

Select a number to change that item, or `y` to proceed. After confirming, you will be prompted to create passwords, then shown a final drive wipe warning before anything destructive runs.

Locale, timezone, and keyboard layout are configured interactively mid-install using the standard Debian ncurses tools.

### Non-VM installs

If no VM is detected, the installer shows a warning and runs `lsblk` so you can see your drives before deciding. You will be asked to confirm twice. Use with care.

### Resume

If an install is interrupted, resume from where it left off:

```bash
sudo ./debianinstall.py --resume
```

## What Gets Installed

The installer writes DEB822 apt sources covering:

- `trixie`, `trixie-updates`, `trixie-backports`
- `trixie-security`
- `main contrib non-free non-free-firmware`

i386 architecture is enabled by default (required for Steam and 32-bit software).

If **Niri + Noctalia** is selected, the Noctalia apt repo is also added:

```
https://pkg.noctalia.dev/apt
```

### Package Profiles

**minimal-tty** — bare minimum: sudo, locales, keyboard-configuration, console-setup

**standard-tty** — adds: ca-certificates, curl, wget, less, vim-tiny, network-manager, openssh-server

`linux-image-amd64` and `systemd-sysv` are installed on top of whichever profile you pick.

The following firmware packages are installed before the kernel on every install, so firmware is baked into the initramfs:

- `firmware-linux` / `firmware-linux-nonfree` — general Linux firmware
- `firmware-amd-graphics` — AMD GPU firmware, required for Niri/Xorg to start on AMD hardware
- `firmware-misc-nonfree` — covers a wide range of USB devices, webcams, and controllers

### Desktop: Niri + Noctalia

When **niri-noctalia** is selected:

- `noctalia-shell` is installed from the Noctalia apt repo (brings in Niri as a dependency)
- `greetd` is installed and configured to autologin your user directly into `niri-session`
- `graphical.target` is set as the default systemd target

When **none** is selected, `multi-user.target` is set and no display stack is installed.

## Interactive Configuration Mid-Install

After packages land, the installer runs the standard Debian ncurses configuration screens:

1. **tzdata** — select your timezone
2. **keyboard-configuration** — select your keyboard layout

These run inside the chroot so your choices apply to the installed system directly.

## Installing a Different Desktop

The installer does not offer other desktop environments directly — it is focused on Niri + Noctalia or TTY. If you want a different DE, boot into your installed system and install it yourself.

### Minimal — manual install

Install just the packages you need and enable the display manager yourself:

```bash
# Example: XFCE
sudo apt install xfce4 lightdm
sudo systemctl enable lightdm
sudo systemctl set-default graphical.target
```

```bash
# Example: KDE Plasma
sudo apt install kde-plasma-desktop sddm
sudo systemctl enable sddm
sudo systemctl set-default graphical.target
```

```bash
# Example: GNOME
sudo apt install gnome-core gdm3
sudo systemctl enable gdm3
sudo systemctl set-default graphical.target
```

### More complete — tasksel

`tasksel` lets you pick a desktop environment from a menu and installs the full recommended package set for it:

```bash
sudo apt install tasksel
sudo tasksel
```

Use the arrow keys to highlight a desktop, press **Space** to select it (an asterisk `*` appears), then press **Enter** to install. After it completes:

```bash
# Enable the display manager that was installed
# KDE → sddm, GNOME → gdm3, XFCE/MATE/Cinnamon → lightdm
sudo systemctl enable <display-manager>
sudo systemctl set-default graphical.target
sudo reboot
```

## After Install

Once all phases are complete you will be asked:

- **Install latest kernel from backports?** — installs `linux-image-amd64` from `trixie-backports` and runs `apt upgrade`
- **Reboot now?** — reboots out of the live environment

## Notes

Right now this is intentionally narrow:

- UEFI + GPT only (no BIOS support)
- amd64 only
- Trixie (Debian testing) as the target release
- Focused on the Niri + Noctalia stack or a clean TTY base
- Proof of concept — use disposable VMs until the warning at the top is removed
