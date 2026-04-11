#!/usr/bin/env python3
"""
Debian Installer Recovery Script
Picks up from after the system-config phase:
  graphical target → fstab → users → niri config → bootloader
Run as root from the live environment with /mnt still accessible.
"""

import getpass
import os
import subprocess
import sys

TARGET = "/mnt"


def run(cmd, input_text=None, display=None):
    label = display or " ".join(str(a) for a in cmd)
    print(f"  + {label}")
    subprocess.run(cmd, check=True, input=input_text, text=True if input_text else False)


def chroot(cmd, input_text=None, display=None):
    run(["chroot", TARGET] + cmd, input_text=input_text, display=display)


def remount_virtual():
    print("[*] Mounting virtual filesystems...")
    mounts = [
        (["mount", "--bind", "/dev", f"{TARGET}/dev"], f"{TARGET}/dev"),
        (["mount", "--bind", "/dev/pts", f"{TARGET}/dev/pts"], f"{TARGET}/dev/pts"),
        (["mount", "-t", "proc", "proc", f"{TARGET}/proc"], f"{TARGET}/proc"),
        (["mount", "-t", "sysfs", "sysfs", f"{TARGET}/sys"], f"{TARGET}/sys"),
        (["mount", "--bind", "/run", f"{TARGET}/run"], f"{TARGET}/run"),
    ]
    for cmd, _ in mounts:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass  # already mounted


def umount_virtual():
    print("[*] Unmounting virtual filesystems...")
    for path in [
        f"{TARGET}/run",
        f"{TARGET}/sys",
        f"{TARGET}/proc",
        f"{TARGET}/dev/pts",
        f"{TARGET}/dev",
    ]:
        try:
            subprocess.run(["umount", "-l", path], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass


def setup_graphical_target(username, desktop):
    print("\n[*] Setting default systemd target...")
    if desktop == "niri-noctalia":
        greetd_config = "\n".join([
            "[terminal]",
            "vt = 1",
            "",
            "[default_session]",
            'command = "niri-session"',
            f'user = "{username}"',
        ])
        chroot(["bash", "-c",
            f"mkdir -p /etc/greetd && cat > /etc/greetd/config.toml <<'EOF'\n{greetd_config}\nEOF"])
        chroot(["systemctl", "enable", "greetd"])
        chroot(["systemctl", "set-default", "graphical.target"])
    else:
        chroot(["systemctl", "set-default", "multi-user.target"])


def write_fstab(disk, filesystem, swap_type, swap_partition, separate_home, home_partition):
    print("\n[*] Writing fstab...")
    efi_part = disk + "1"

    if swap_type == "partition":
        root_part = disk + "3"
    else:
        root_part = disk + "2"

    if separate_home and not home_partition:
        home_partition = disk + ("4" if swap_type == "partition" else "3")

    blkid_vars = [
        f'root_uuid=$(/sbin/blkid -s UUID -o value {root_part})',
        f'efi_uuid=$(/sbin/blkid -s UUID -o value {efi_part})',
    ]
    if separate_home:
        blkid_vars.append(f'home_uuid=$(/sbin/blkid -s UUID -o value {home_partition})')
    if swap_type == "partition":
        blkid_vars.append(f'swap_uuid=$(/sbin/blkid -s UUID -o value {swap_partition})')

    if filesystem == "btrfs":
        root_line = 'UUID="${root_uuid}" / btrfs subvol=@,compress=zstd,noatime 0 0'
    elif filesystem == "xfs":
        root_line = 'UUID="${root_uuid}" / xfs defaults 0 1'
    else:
        root_line = 'UUID="${root_uuid}" / ext4 defaults 0 1'

    fstab_lines = [
        root_line,
        'UUID="${efi_uuid}" /boot/efi vfat umask=0077 0 1',
    ]
    if filesystem == "btrfs" and not separate_home:
        fstab_lines.append('UUID="${root_uuid}" /home btrfs subvol=@home,compress=zstd,noatime 0 0')
    if separate_home:
        fstab_lines.append('UUID="${home_uuid}" /home ext4 defaults 0 2')
    if swap_type == "partition":
        fstab_lines.append('UUID="${swap_uuid}" none swap sw 0 0')
    if swap_type == "swapfile":
        fstab_lines.append('/swapfile none swap sw 0 0')

    fstab_content = "\n".join(fstab_lines)
    shell = " && ".join(blkid_vars) + f" && cat > /etc/fstab <<EOF\n{fstab_content}\nEOF"
    chroot(["bash", "-lc", shell])


def create_users(username, root_password, user_password):
    print("\n[*] Creating users...")
    chroot(["adduser", "--disabled-password", "--gecos", "", username])
    chroot(["usermod", "-aG", "sudo", username])
    chroot(["chpasswd"], input_text=f"root:{root_password}\n", display="chroot /mnt chpasswd <redacted>")
    chroot(["chpasswd"], input_text=f"{username}:{user_password}\n",
           display=f"chroot /mnt chpasswd <redacted:{username}>")


def write_niri_config(username):
    print("\n[*] Writing niri config...")
    cmd = (
        f"mkdir -p /home/{username}/.config/niri && "
        f"cp /usr/share/niri/default-config.kdl /home/{username}/.config/niri/config.kdl 2>/dev/null || true && "
        f"echo 'spawn-at-startup \"qs\" \"-c\" \"noctalia-shell\"' >> /home/{username}/.config/niri/config.kdl && "
        f"chown -R {username}:{username} /home/{username}/.config"
    )
    chroot(["bash", "-lc", cmd])


def install_bootloader():
    print("\n[*] Installing bootloader...")
    chroot(["apt", "install", "-y", "grub-efi-amd64"])
    chroot(["grub-install", "--target=x86_64-efi", "--efi-directory=/boot/efi",
            "--bootloader-id=debian", "--removable"])
    chroot(["update-grub"])


def main():
    if os.geteuid() != 0:
        print("Run as root (sudo).")
        sys.exit(1)

    print("=" * 50)
    print("  Debian Installer Recovery")
    print("  Phases: graphical target → fstab → users → niri config → bootloader")
    print("=" * 50)
    print()

    username = input("Username: ").strip()
    root_password = getpass.getpass("Root password: ")
    user_password = getpass.getpass(f"Password for {username}: ")
    desktop = input("Desktop [niri-noctalia/none] (default: niri-noctalia): ").strip() or "niri-noctalia"
    filesystem = input("Filesystem [ext4/btrfs/xfs] (default: ext4): ").strip() or "ext4"
    disk = input("Disk (e.g. /dev/vda): ").strip()
    swap_type = input("Swap type [none/swapfile/partition] (default: none): ").strip() or "none"
    swap_partition = ""
    if swap_type == "partition":
        swap_partition = input("Swap partition (e.g. /dev/vda2): ").strip()
    separate_home_input = input("Separate /home partition? [y/N]: ").strip().lower()
    separate_home = separate_home_input == "y"
    home_partition = ""
    if separate_home:
        home_partition = input("Home partition (e.g. /dev/vda3): ").strip()

    print()
    remount_virtual()

    try:
        setup_graphical_target(username, desktop)
        write_fstab(disk, filesystem, swap_type, swap_partition, separate_home, home_partition)
        create_users(username, root_password, user_password)
        if desktop == "niri-noctalia":
            write_niri_config(username)
        install_bootloader()
    finally:
        umount_virtual()

    print()
    print("=" * 50)
    print("  Recovery complete. You can now reboot.")
    print("=" * 50)


if __name__ == "__main__":
    main()
