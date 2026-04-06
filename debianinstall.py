#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from shutil import which
from typing import Any

VERSION = 'v0.0.5'
BANNER_URL = 'https://github.com/linuxgamerlife/debianinstaller'

PHASES: tuple[str, ...] = (
    'partition',
    'format',
    'mount',
    'bootstrap',
    'virtual-mounts',
    'sources',
    'packages',
    'interactive-config',
    'system-config',
    'fstab',
    'users',
    'bootloader',
)

PACKAGE_PROFILES: dict[str, list[str]] = {
    'minimal-tty': [
        'sudo',
        'locales',
        'keyboard-configuration',
        'console-setup',
        'tasksel',
    ],
    'standard-tty': [
        'sudo',
        'locales',
        'keyboard-configuration',
        'console-setup',
        'ca-certificates',
        'curl',
        'wget',
        'less',
        'vim-tiny',
        'network-manager',
        'openssh-server',
        'tasksel',
    ],
}

VM_HINT_PATHS = (
    Path('/sys/class/dmi/id/product_name'),
    Path('/sys/class/dmi/id/sys_vendor'),
)
VM_HINT_TOKENS = ('kvm', 'qemu', 'virtualbox', 'vmware', 'bochs', 'hyper-v')
HOSTNAME_PATTERN = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
USERNAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_-]*[$]?$')
SUFFIXLESS_PREFIXES = ('/dev/nvme', '/dev/mmcblk')
REQUIRED_COMMANDS = (
    'fdisk',
    'mount',
    'umount',
    'chroot',
    '/sbin/mkfs.ext4',
    '/sbin/blkid',
)

LIVE_PREREQUISITE_PACKAGES = (
    'debootstrap',
    'dosfstools',
    'grub-efi-amd64',
)


class InstallerError(RuntimeError):
    pass


@dataclass(slots=True)
class Config:
    disk: str = '/dev/vda'
    hostname: str = 'debian-vm'
    username: str = 'debian'
    root_password: str | None = None
    user_password: str | None = None
    package_profile: str = 'standard-tty'
    release: str = 'trixie'
    mirror: str = 'https://deb.debian.org/debian'
    efi_size: str = '512M'
    target_mount: str = '/mnt'
    boot_mode: str = 'uefi'
    mode: str = 'apply'
    confirm_disk: str | None = None
    state_file: str = '/var/tmp/debianinstall-state.json'
    log_file: str | None = None
    skip_vm_check: bool = False

    @property
    def execute(self) -> bool:
        return self.mode == 'apply'

    def partition_path(self, number: int) -> str:
        separator = 'p' if self.disk.startswith(SUFFIXLESS_PREFIXES) else ''
        return f'{self.disk}{separator}{number}'

    @property
    def efi_partition(self) -> str:
        return self.partition_path(1)

    @property
    def root_partition(self) -> str:
        return self.partition_path(2)

    @property
    def efi_mount(self) -> str:
        return f'{self.target_mount}/boot/efi'


@dataclass(slots=True)
class State:
    config: Config
    completed_phases: list[str] = field(default_factory=list)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    os.system('clear')
    print(render_banner())
    print()

    try:
        if args.resume:
            config, completed = load_state(Path(args.state_file))
            if args.confirm_disk:
                config.confirm_disk = args.confirm_disk
            if args.log_file:
                config.log_file = args.log_file
        else:
            config = config_from_args(args)
            completed = []

        if args.interactive or not args.disk:
            config = run_interactive_setup(config)

        if config.execute and 'users' not in completed:
            config = ensure_passwords(config)

        if config.execute:
            if not looks_like_vm() and not config.skip_vm_check:
                if not confirm_non_vm_install():
                    print('\nAborted.')
                    return 0
                config.skip_vm_check = True
            if not confirm_apply(config):
                print('\nAborted.')
                return 0

        validate_config(config)
        state = State(config=config, completed_phases=completed)
        print(render_summary(state))
        warnings = collect_warnings(config)
        run(state)
    except InstallerError as exc:
        print(f'\nInstaller error: {exc}')
        return 2
    except KeyboardInterrupt:
        print('\nInterrupted.')
        return 130

    if warnings:
        print('\nWarnings:')
        for warning in warnings:
            print(f'- {warning}')

    print('\nInstall completed.')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Single-file Debian TTY installer v1')
    parser.add_argument('--disk', help='target disk, for example /dev/vda')
    parser.add_argument('--hostname', help='hostname for the installed system')
    parser.add_argument('--username', help='primary user account name')
    parser.add_argument('--root-password', help='root password for apply mode')
    parser.add_argument('--user-password', help='primary user password for apply mode')
    parser.add_argument('--package-profile', choices=sorted(PACKAGE_PROFILES), help='base package profile')
    parser.add_argument('--confirm-disk', help='must exactly match --disk to confirm destructive install')
    parser.add_argument('--state-file', default='/var/tmp/debianinstall-state.json')
    parser.add_argument('--log-file', help='optional command log')
    parser.add_argument('--interactive', action='store_true', help='launch interactive setup')
    parser.add_argument('--resume', action='store_true', help='resume from saved state file')
    return parser


def config_from_args(args: argparse.Namespace) -> Config:
    return Config(
        disk=args.disk or '/dev/vda',
        hostname=args.hostname or 'debian-vm',
        username=args.username or 'debian',
        root_password=args.root_password,
        user_password=args.user_password,
        package_profile=args.package_profile or 'standard-tty',
        confirm_disk=args.confirm_disk,
        state_file=args.state_file,
        log_file=args.log_file,
    )


def make_box(lines: list[str], *, align: str = 'center') -> str:
    width = max(len(l) for l in lines)
    border = '-' * (width + 4)
    result = [border]
    for line in lines:
        if align == 'center':
            result.append(f'| {line.center(width)} |')
        else:
            result.append(f'| {line:<{width}} |')
    result.append(border)
    return '\n'.join(result)


def render_banner() -> str:
    return make_box([
        f'LGL Debian Installer {VERSION}',
        '100% Vibe Coded',
        'Intelligently Prompted',
        BANNER_URL,
    ])


def run_interactive_setup(config: Config) -> Config:
    print('Step 1: Select disk')
    print('Available disks:\n')
    subprocess.run(['lsblk', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT'], check=False)
    config.disk = prompt_disk(config.disk)

    print('\nStep 2: What would you like your hostname to be?')
    config.hostname = prompt_text('Hostname', config.hostname)

    print('\nStep 3: What username would you like to use?')
    config.username = prompt_text('Username', config.username)

    print('\nStep 4: Which package profile do you want?')
    print('  minimal-tty  — bare minimum to boot and log in')
    print('  standard-tty — adds networking, SSH, curl, wget, vim')
    config.package_profile = prompt_profile(config.package_profile)

    print('\nStep 5: State file')
    print('  The state file records completed phases so the install can resume if interrupted.')
    config.state_file = prompt_text('State file', config.state_file)

    while True:
        os.system('clear')
        print(render_banner())
        print('\nThank you. I have all the info I need to get started.')
        print('Check the summary below and confirm you want to continue.\n')
        print(render_summary_menu(config))
        choice = input('\nSelect number to change, or y to continue: ').strip().lower()

        if choice == 'y':
            return config

        if choice.isdigit():
            n = int(choice)
            if n == 1:
                print('\nAvailable disks:\n')
                subprocess.run(['lsblk', '-o', 'NAME,SIZE,TYPE,MOUNTPOINT'], check=False)
                config.disk = prompt_disk(config.disk)
            elif n == 2:
                config.hostname = prompt_text('Hostname', config.hostname)
            elif n == 3:
                config.username = prompt_text('Username', config.username)
            elif n == 4:
                config.package_profile = prompt_profile(config.package_profile)
            elif n == 5:
                config.state_file = prompt_text('State file', config.state_file)
        else:
            print('Invalid choice.')


def prompt_disk(current: str) -> str:
    while True:
        value = input(f'\nDisk [{current}]: ').strip() or current
        confirm = input(f'Use {value}? This will erase all data on it. [y/N]: ').strip().lower()
        if confirm == 'y':
            return value
        print('OK, let\'s pick again.')


def render_summary_menu(config: Config) -> str:
    return '\n'.join([
        f'1. disk:            {config.disk}',
        f'2. hostname:        {config.hostname}',
        f'3. username:        {config.username}',
        f'4. package profile: {config.package_profile}',
        f'5. state file:      {config.state_file}',
    ])


def confirm_non_vm_install() -> bool:
    print()
    print(make_box([
        'WARNING: No VM detected. Are you sure you want to continue?',
        'Continuing without knowing what you are doing might be bad!',
    ], align='left'))
    answer = input('\nContinue anyway? [y/N]: ').strip().lower()
    if answer != 'y':
        return False
    print()
    subprocess.run(['lsblk'], check=False)
    print()
    answer = input('Still sure? [y/N]: ').strip().lower()
    return answer == 'y'


def confirm_apply(config: Config) -> bool:
    disk_name = Path(config.disk).name
    print()
    print(make_box([
        'Are you sure you want to continue?',
        'This will delete ALL data on:',
        f'Drive: {disk_name}',
    ], align='left'))
    answer = input(f'\nType the disk name to confirm [{disk_name}]: ').strip()
    if answer == disk_name:
        config.confirm_disk = config.disk
        return True
    print('Disk name did not match — returning to summary.')
    return False


def prompt_text(label: str, current: str) -> str:
    value = input(f'{label} [{current}]: ').strip()
    return value or current



def prompt_profile(current: str) -> str:
    profiles = sorted(PACKAGE_PROFILES)
    for index, profile in enumerate(profiles, start=1):
        print(f'{index}. {profile}')
    choice = input(f'Package profile [current: {current}]: ').strip()
    if not choice:
        return current
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx]
    if choice in PACKAGE_PROFILES:
        return choice
    print('Invalid profile; keeping current value.')
    return current


def ensure_passwords(config: Config) -> Config:
    if not config.root_password:
        config.root_password = prompt_password('root')
    if not config.user_password:
        config.user_password = prompt_password(config.username)
    return config


def prompt_password(label: str) -> str:
    first = getpass.getpass(f'Create password for {label}: ')
    second = getpass.getpass(f'Confirm password for {label}: ')
    if not first:
        raise InstallerError(f'password for {label} cannot be empty')
    if first != second:
        raise InstallerError(f'password confirmation for {label} did not match')
    return first


def validate_config(config: Config) -> None:
    if not config.disk.startswith(('/dev/vd', '/dev/sd', '/dev/nvme', '/dev/mmcblk')):
        raise InstallerError(f"unsupported disk path '{config.disk}'")
    if config.boot_mode != 'uefi':
        raise InstallerError('v1 only supports UEFI installs')
    if not HOSTNAME_PATTERN.fullmatch(config.hostname):
        raise InstallerError(f"invalid hostname '{config.hostname}'")
    if not USERNAME_PATTERN.fullmatch(config.username):
        raise InstallerError(f"invalid username '{config.username}'")
    if config.package_profile not in PACKAGE_PROFILES:
        raise InstallerError(f"unknown package profile '{config.package_profile}'")
    if config.execute:
        if os.geteuid() != 0:
            raise InstallerError('apply mode requires root')
        if not Path('/sys/firmware/efi').exists():
            raise InstallerError('apply mode requires a UEFI booted environment')
        if not looks_like_vm() and not config.skip_vm_check:
            raise InstallerError('apply mode is blocked because this host does not look like a VM')
        if config.confirm_disk != config.disk:
            raise InstallerError('apply mode requires --confirm-disk to exactly match --disk')
        if not Path(config.disk).exists():
            raise InstallerError(f'target disk does not exist: {config.disk}')
        if mountpoint_busy(Path(config.target_mount)):
            raise InstallerError(f'target mount path appears busy: {config.target_mount}')
        missing = missing_commands()
        if missing:
            raise InstallerError('required host commands are missing: ' + ', '.join(missing))


def collect_warnings(config: Config) -> list[str]:
    warnings: list[str] = []
    if not looks_like_vm():
        warnings.append('host does not look like a VM; this installer is intended only for disposable VMs')
    if not Path('/sys/firmware/efi').exists():
        warnings.append('UEFI firmware directory is not present on this system')
    if not Path(config.disk).exists():
        warnings.append(f'target disk does not exist on this system: {config.disk}')
    if mountpoint_busy(Path(config.target_mount)):
        warnings.append(f'target mount path already exists and may be in use: {config.target_mount}')
    if os.geteuid() != 0:
        warnings.append('installer is not running as root')
    missing = missing_commands()
    if missing:
        warnings.append('required host commands are missing: ' + ', '.join(missing))
    if config.execute:
        warnings.append('apply mode will install live-environment prerequisites: ' + ', '.join(LIVE_PREREQUISITE_PACKAGES))
    return warnings


def render_summary(state: State) -> str:
    config = state.config
    return '\n'.join(
        [
            'debianinstall v1',
            f'  disk: {config.disk}',
            f'  efi partition: {config.efi_partition}',
            f'  root partition: {config.root_partition}',
            f'  hostname: {config.hostname}',
            f'  username: {config.username}',
            f'  package profile: {config.package_profile}',
            f'  state file: {config.state_file}',
            f'  completed phases: {", ".join(state.completed_phases) if state.completed_phases else "none"}',
        ]
    )


def run(state: State) -> None:
    save_state(state)
    if state.config.execute:
        install_live_prerequisites(state)
    try:
        for phase in PHASES:
            if phase in state.completed_phases:
                continue
            run_phase(phase, state)
            state.completed_phases.append(phase)
            save_state(state)
        if state.config.execute:
            print('\nAlmost there! A few final optional steps before we finish.')
            prompt_backports_kernel(state)
    finally:
        if state.config.execute and has_active_mounts(Path(state.config.target_mount)):
            try:
                cleanup(state)
            except subprocess.CalledProcessError as exc:
                print(f'[cleanup] best-effort cleanup failed: {exc}')
    if state.config.execute:
        prompt_reboot()


def run_phase(phase: str, state: State) -> None:
    if phase == 'partition':
        partition_disk(state)
    elif phase == 'format':
        format_filesystems(state)
    elif phase == 'mount':
        mount_target(state)
    elif phase == 'bootstrap':
        bootstrap(state)
    elif phase == 'virtual-mounts':
        mount_virtual(state)
    elif phase == 'sources':
        write_sources(state)
    elif phase == 'packages':
        install_packages(state)
    elif phase == 'interactive-config':
        interactive_config(state)
    elif phase == 'system-config':
        configure_system(state)
    elif phase == 'fstab':
        write_fstab(state)
    elif phase == 'users':
        create_users(state)
    elif phase == 'bootloader':
        install_bootloader(state)
    else:
        raise InstallerError(f'unknown phase {phase}')


def partition_disk(state: State) -> None:
    config = state.config
    script = '\n'.join([
        'g', 'n', '', '', f'+{config.efi_size}' if not config.efi_size.startswith('+') else config.efi_size,
        't', '1', 'n', '', '', '', 'w',
    ]) + '\n'
    run_command(['fdisk', config.disk], phase='partition', state=state, input_text=script)


def format_filesystems(state: State) -> None:
    config = state.config
    run_command(['/sbin/mkfs.ext4', config.root_partition], phase='format-root', state=state)
    run_command(['/sbin/mkfs.fat', '-F32', config.efi_partition], phase='format-efi', state=state)


def mount_target(state: State) -> None:
    config = state.config
    run_command(['mount', config.root_partition, config.target_mount], phase='mount-root', state=state)
    run_command(['mkdir', '-p', config.efi_mount], phase='mount-efi', state=state)
    run_command(['mount', '-t', 'vfat', config.efi_partition, config.efi_mount], phase='mount-efi', state=state)


def bootstrap(state: State) -> None:
    config = state.config
    run_command(['debootstrap', config.release, config.target_mount, config.mirror], phase='bootstrap', state=state)


def mount_virtual(state: State) -> None:
    target = state.config.target_mount
    run_command(['mount', '-t', 'proc', 'proc', f'{target}/proc'], phase='mount-virtual', state=state)
    run_command(['mount', '-t', 'sysfs', 'sysfs', f'{target}/sys'], phase='mount-virtual', state=state)
    run_command(['mount', '--rbind', '/dev', f'{target}/dev'], phase='mount-virtual', state=state)


def install_live_prerequisites(state: State) -> None:
    run_command(['apt-get', 'update'], phase='host-apt-update', state=state)
    run_command(['apt-get', 'install', '-y', *LIVE_PREREQUISITE_PACKAGES], phase='host-install-prereqs', state=state)


def write_sources(state: State) -> None:
    config = state.config
    target = config.target_mount
    release = config.release
    main_sources = '\n'.join([
        'Types: deb',
        f'URIs: {config.mirror}',
        f'Suites: {release} {release}-updates {release}-backports',
        'Components: main contrib non-free non-free-firmware',
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg',
    ])
    security_sources = '\n'.join([
        'Types: deb',
        'URIs: https://security.debian.org/debian-security',
        f'Suites: {release}-security',
        'Components: main contrib non-free non-free-firmware',
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg',
    ])
    run_command(
        ['bash', '-c', f"cat > {target}/etc/apt/sources.list.d/debian.sources <<'EOF'\n{main_sources}\nEOF"],
        phase='sources-main', state=state,
    )
    run_command(
        ['bash', '-c', f"cat > {target}/etc/apt/sources.list.d/debian-security.sources <<'EOF'\n{security_sources}\nEOF"],
        phase='sources-security', state=state,
    )
    # Remove the legacy sources.list left by debootstrap
    run_command(['rm', '-f', f'{target}/etc/apt/sources.list'], phase='sources-cleanup', state=state)
    # Enable i386 for Steam and other 32-bit software
    run_in_chroot(state, ['dpkg', '--add-architecture', 'i386'], phase='add-i386')
    run_in_chroot(state, ['apt', 'update'], phase='sources-apt-update')


def interactive_config(state: State) -> None:
    """Run interactive debconf dialogs inside the chroot for locale, timezone, keyboard, and DE selection."""
    config = state.config
    target = config.target_mount
    # These must run without DEBIAN_FRONTEND=noninteractive so the ncurses UI appears
    for cmd, phase in [
        (['dpkg-reconfigure', 'locales'], 'interactive-locales'),
        (['dpkg-reconfigure', 'tzdata'], 'interactive-tzdata'),
        (['dpkg-reconfigure', 'keyboard-configuration'], 'interactive-keyboard'),
        (['tasksel'], 'interactive-tasksel'),
    ]:
        chroot_cmd = ['chroot', target, *cmd]
        rendered = render_command(chroot_cmd)
        line = f'[{phase}] {rendered}'
        append_log(config, line)
        print(line)
        if config.execute:
            subprocess.run(chroot_cmd, check=True)


def setup_graphical_target(state: State) -> None:
    config = state.config
    target = config.target_mount
    dm_candidates = [
        ('sddm', 'sddm'),       # KDE, LXQt
        ('gdm3', 'gdm3'),       # GNOME
        ('lightdm', 'lightdm'), # XFCE, MATE, Cinnamon, LXDE
    ]
    dm_service = None
    if config.execute:
        for pkg, service in dm_candidates:
            result = subprocess.run(
                ['chroot', target, 'dpkg-query', '-W', '-f=${Status}', pkg],
                capture_output=True, text=True,
            )
            if 'install ok installed' in result.stdout:
                dm_service = service
                break
        if dm_service:
            run_in_chroot(state, ['systemctl', 'enable', dm_service], phase='enable-dm')
            run_in_chroot(state, ['systemctl', 'set-default', 'graphical.target'], phase='graphical-target')
        else:
            run_in_chroot(state, ['systemctl', 'set-default', 'multi-user.target'], phase='default-target')
            print('[setup-graphical] no display manager detected — set multi-user.target')
    else:
        print('[setup-graphical] (plan) would detect display manager and enable graphical.target if found')


def install_packages(state: State) -> None:
    config = state.config
    run_in_chroot(state, ['apt', 'update'], phase='apt-update')
    packages = ['linux-image-amd64', 'systemd-sysv', *PACKAGE_PROFILES[config.package_profile]]
    run_in_chroot(state, ['apt', 'install', '-y', *packages], phase='install-packages')


def configure_system(state: State) -> None:
    config = state.config
    hostname = shlex.quote(config.hostname)
    hosts_content = '\n'.join(['127.0.0.1 localhost', f'127.0.1.1 {config.hostname}'])
    run_in_chroot(state, ['bash', '-lc', f"printf '%s\\n' {hostname} > /etc/hostname"], phase='hostname')
    run_in_chroot(state, ['bash', '-lc', f"cat > /etc/hosts <<'EOF'\n{hosts_content}\nEOF"], phase='hosts')
    if config.package_profile == 'standard-tty':
        run_in_chroot(state, ['systemctl', 'enable', 'NetworkManager'], phase='services')
        run_in_chroot(state, ['systemctl', 'enable', 'ssh'], phase='services')
    setup_graphical_target(state)


def write_fstab(state: State) -> None:
    config = state.config
    shell = ' && '.join([
        f'root_uuid=$(/sbin/blkid -s UUID -o value {config.root_partition})',
        f'efi_uuid=$(/sbin/blkid -s UUID -o value {config.efi_partition})',
        'cat > /etc/fstab <<EOF\nUUID="${root_uuid}" / ext4 defaults 0 1\nUUID="${efi_uuid}" /boot/efi vfat umask=0077 0 1\nEOF',
    ])
    run_command(['chroot', config.target_mount, 'bash', '-lc', shell], phase='fstab', state=state)


def create_users(state: State) -> None:
    config = state.config
    run_in_chroot(state, ['adduser', '--disabled-password', '--gecos', '', config.username], phase='user')
    run_in_chroot(state, ['usermod', '-aG', 'sudo', config.username], phase='user')
    run_in_chroot(
        state,
        ['chpasswd'],
        phase='root-password',
        input_text=f"root:{config.root_password or '<unset>'}\n",
        display_command='chroot /mnt chpasswd <redacted>',
    )
    run_in_chroot(
        state,
        ['chpasswd'],
        phase='user-password',
        input_text=f"{config.username}:{config.user_password or '<unset>'}\n",
        display_command=f'chroot /mnt chpasswd <redacted:{config.username}>',
    )


def install_bootloader(state: State) -> None:
    run_in_chroot(state, ['apt', 'install', '-y', 'grub-efi-amd64'], phase='install-grub')
    run_in_chroot(state, ['grub-install', '--target=x86_64-efi', '--efi-directory=/boot/efi', '--bootloader-id=debian', '--removable'], phase='grub-install')
    run_in_chroot(state, ['update-grub'], phase='grub-config')


def prompt_backports_kernel(state: State) -> None:
    print()
    print(make_box([
        f'Install latest kernel from {state.config.release}-backports?',
        'This gives you the newest kernel available for',
        f'{state.config.release}. Recommended for latest hardware support.',
        'Press y to install, or Enter to skip.',
    ], align='left'))
    answer = input('\n[y/N]: ').strip().lower()
    if answer != 'y':
        return
    run_in_chroot(state, ['apt', 'install', '-y', '-t', f'{state.config.release}-backports', 'linux-image-amd64'], phase='backports-kernel')
    run_in_chroot(state, ['apt', 'upgrade', '-y'], phase='backports-upgrade')


def prompt_reboot() -> None:
    print()
    print(make_box([
        'Reboot?',
        'The install is complete. Reboot now to boot into',
        'your new system.',
    ], align='left'))
    answer = input('\n[y/N]: ').strip().lower()
    if answer == 'y':
        subprocess.run(['reboot'], check=False)


def cleanup(state: State) -> None:
    target = state.config.target_mount
    cleanup_shells = [
        f"mountpoint -q {target}/dev/pts && umount -l {target}/dev/pts || true",
        f"mountpoint -q {target}/dev && umount -R {target}/dev || true",
        f"mountpoint -q {target}/proc && umount {target}/proc || true",
        f"mountpoint -q {target}/sys && umount {target}/sys || true",
        f"mountpoint -q {target}/boot/efi && umount {target}/boot/efi || true",
        f"mountpoint -q {target} && umount {target} || true",
    ]
    for shell_command in cleanup_shells:
        run_command(['bash', '-lc', shell_command], phase='cleanup', state=state)


def run_in_chroot(
    state: State,
    command: list[str],
    *,
    phase: str,
    input_text: str | None = None,
    display_command: list[str] | str | None = None,
) -> None:
    run_command(
        ['chroot', state.config.target_mount, *command],
        phase=phase,
        state=state,
        input_text=input_text,
        display_command=display_command,
    )


def run_command(
    command: list[str],
    *,
    phase: str,
    state: State,
    input_text: str | None = None,
    display_command: list[str] | str | None = None,
) -> None:
    rendered = render_command(display_command if display_command is not None else command)
    line = f'[{phase}] {rendered}'
    append_log(state.config, line)
    print(line)
    if not state.config.execute:
        return
    subprocess.run(command, input=input_text, text=True, check=True)


def render_command(command: list[str] | str) -> str:
    if isinstance(command, str):
        return command
    return shlex.join(command)


def append_log(config: Config, line: str) -> None:
    if not config.log_file:
        return
    path = Path(config.log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(line)
        handle.write('\n')


def save_state(state: State) -> None:
    path = Path(state.config.state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        'config': serialize_config(state.config),
        'completed_phases': state.completed_phases,
    }
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def load_state(path: Path) -> tuple[Config, list[str]]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    config = Config(**payload['config'])
    return config, list(payload.get('completed_phases', []))


def serialize_config(config: Config) -> dict[str, Any]:
    data = asdict(config)
    data['root_password'] = None
    data['user_password'] = None
    return data


def looks_like_vm() -> bool:
    for path in VM_HINT_PATHS:
        try:
            value = path.read_text(encoding='utf-8', errors='ignore').strip().lower()
        except OSError:
            continue
        if any(token in value for token in VM_HINT_TOKENS):
            return True
    return False


def mountpoint_busy(path: Path) -> bool:
    return has_active_mounts(path) or (path.exists() and any(path.iterdir()))


def has_active_mounts(target: Path) -> bool:
    try:
        mountinfo = Path('/proc/self/mountinfo').read_text(encoding='utf-8')
    except OSError:
        return False
    resolved = str(target.resolve())
    for line in mountinfo.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        mount_point = unescape_mount_field(parts[4])
        if mount_point == resolved or mount_point.startswith(f'{resolved}/'):
            return True
    return False


def unescape_mount_field(value: str) -> str:
    return value.replace('\\040', ' ').replace('\\011', '\t').replace('\\012', '\n').replace('\\134', '\\')


def missing_commands() -> list[str]:
    missing: list[str] = []
    for command in REQUIRED_COMMANDS:
        if command.startswith('/'):
            if not Path(command).exists():
                missing.append(command)
        elif which(command) is None:
            missing.append(command)
    return missing


if __name__ == '__main__':
    raise SystemExit(main())
