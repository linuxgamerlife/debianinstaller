# Debian Installer

This exists because I was curious whether you can get something close to the same experience as Arch, but on Debian.

It is 100% vibecoded, but intelligently prompted by me.

This is a proof of concept. One thing I like about Arch is the build-from-nothing aspect, and this project is an attempt to get a similar feel with a Debian base install.

## Current Scope

This is built for VMs only right now so you do not accidentally screw up your actual install.

The current goal is simple:

- start from a Debian live environment in a VM
- run the installer from TTY
- install a minimal Debian system to disk
- reboot back into a TTY login
- install whatever desktop environment you want afterwards

## Prerequisites

Inside the Debian live environment:

```bash
sudo apt install git
```

Then:

```bash
git clone https://github.com/linuxgamerlife/debianinstaller
cd debianinstaller
chmod +x debianinstaller.py
sudo ./debianinstaller.py
```

## Usage

Run the installer, then select options to change them.

The installer is intended to guide a basic VM install and return you to a usable TTY system once complete.

## After Install

Once complete, reboot.

You should come back to a TTY where you can log in and install whatever desktop environment you want.

## KDE Examples

Minimal KDE:

```bash
sudo apt update
sudo apt install kde-plasma-desktop
```

Full KDE install:

```bash
sudo apt install task-kde-desktop
```

Then enable graphical boot:

```bash
sudo systemctl set-default graphical-target
sudo systemctl enable --now sddm
```

Once complete, reboot.

## Notes

Right now this is intentionally narrow:

- VM use only
- proof of concept
- focused on the install-from-scratch feel
- desktop environment setup comes after the base install

If you use it, treat it like an experiment and use disposable VMs.
