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

PHASES: tuple[str, ...] = (
    'partition',
    'format',
    'mount',
    'bootstrap',
    'virtual-mounts',
    'packages',
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
    ],
}

VM_HINT_PATHS = (
    Path('/sys/class/dmi/id/product_name'),
    Path('/sys/class/dmi/id/sys_vendor'),
)
VM_HINT_TOKENS = ('kvm', 'qemu', 'virtualbox', 'vmware', 'bochs', 'hyper-v')
HOSTNAME_PATTERN = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')
USERNAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_-]*[$]?$')
KEYBOARD_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
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
    locale: str = 'en_GB.UTF-8'
    timezone: str = 'Europe/London'
    keyboard_layout: str = 'gb'
    package_profile: str = 'standard-tty'
    release: str = 'trixie'
    mirror: str = 'https://deb.debian.org/debian'
    efi_size: str = '512M'
    target_mount: str = '/mnt'
    boot_mode: str = 'uefi'
    mode: str = 'plan'
    confirm_disk: str | None = None
    state_file: str = '/var/tmp/debianinstall-v1-state.json'
    log_file: str | None = None

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

    try:
        if args.resume:
            config, completed = load_state(Path(args.state_file))
            config.mode = args.mode or config.mode
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

    if config.execute:
        print('\nApply mode completed.')
    else:
        print('\nPlan mode only. No install commands were executed.')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Single-file Debian TTY installer v1')
    parser.add_argument('--disk', help='target disk, for example /dev/vda')
    parser.add_argument('--hostname', help='hostname for the installed system')
    parser.add_argument('--username', help='primary user account name')
    parser.add_argument('--root-password', help='root password for apply mode')
    parser.add_argument('--user-password', help='primary user password for apply mode')
    parser.add_argument('--locale', help='default locale, for example en_GB.UTF-8')
    parser.add_argument('--timezone', help='timezone, for example Europe/London')
    parser.add_argument('--keyboard-layout', help='console keyboard layout, for example gb or us')
    parser.add_argument('--package-profile', choices=sorted(PACKAGE_PROFILES), help='base package profile')
    parser.add_argument('--mode', choices=['plan', 'apply'], default='plan')
    parser.add_argument('--confirm-disk', help='required in apply mode and must exactly match --disk')
    parser.add_argument('--state-file', default='/var/tmp/debianinstall-v1-state.json')
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
        locale=args.locale or 'en_GB.UTF-8',
        timezone=args.timezone or 'Europe/London',
        keyboard_layout=args.keyboard_layout or 'gb',
        package_profile=args.package_profile or 'standard-tty',
        mode=args.mode,
        confirm_disk=args.confirm_disk,
        state_file=args.state_file,
        log_file=args.log_file,
    )


def run_interactive_setup(config: Config) -> Config:
    while True:
        print(render_menu(config))
        choice = input('Select item to edit [1-9], or press Enter to continue: ').strip()
        if not choice:
            if config.execute:
                confirmation = input(f'Type the target disk to confirm destructive apply [{config.disk}]: ').strip()
                config.confirm_disk = confirmation or config.confirm_disk
            return config
        if choice == '1':
            config.disk = prompt_text('Target disk', config.disk)
        elif choice == '2':
            config.hostname = prompt_text('Hostname', config.hostname)
        elif choice == '3':
            config.username = prompt_text('Username', config.username)
        elif choice == '4':
            config.locale = prompt_text('Locale', config.locale)
        elif choice == '5':
            config.timezone = prompt_text('Timezone', config.timezone)
        elif choice == '6':
            config.keyboard_layout = prompt_text('Keyboard layout', config.keyboard_layout)
        elif choice == '7':
            config.package_profile = prompt_profile(config.package_profile)
        elif choice == '8':
            config.mode = prompt_mode(config.mode)
        elif choice == '9':
            config.state_file = prompt_text('State file', config.state_file)
        else:
            print('Invalid choice.')


def render_menu(config: Config) -> str:
    return '\n'.join(
        [
            '',
            'Debian Installer v1',
            f'1. disk: {config.disk}',
            f'2. hostname: {config.hostname}',
            f'3. username: {config.username}',
            f'4. locale: {config.locale}',
            f'5. timezone: {config.timezone}',
            f'6. keyboard layout: {config.keyboard_layout}',
            f'7. package profile: {config.package_profile}',
            f'8. mode: {config.mode}',
            f'9. state file: {config.state_file}',
            '',
            'Whole-disk GPT install: EFI + ext4 root.',
            'Press Enter to continue.',
        ]
    )


def prompt_text(label: str, current: str) -> str:
    value = input(f'{label} [{current}]: ').strip()
    return value or current


def prompt_mode(current: str) -> str:
    print('1. plan')
    print('2. apply')
    choice = input(f'Mode [current: {current}]: ').strip()
    if choice == '2':
        return 'apply'
    if choice in ('', '1'):
        return 'plan'
    print('Invalid mode; keeping current value.')
    return current


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
    first = getpass.getpass(f'Enter password for {label}: ')
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
    if not KEYBOARD_PATTERN.fullmatch(config.keyboard_layout):
        raise InstallerError(f"invalid keyboard layout '{config.keyboard_layout}'")
    if config.package_profile not in PACKAGE_PROFILES:
        raise InstallerError(f"unknown package profile '{config.package_profile}'")
    if config.execute:
        if os.geteuid() != 0:
            raise InstallerError('apply mode requires root')
        if not Path('/sys/firmware/efi').exists():
            raise InstallerError('apply mode requires a UEFI booted environment')
        if not looks_like_vm():
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
            f'  mode: {config.mode}',
            f'  disk: {config.disk}',
            f'  efi partition: {config.efi_partition}',
            f'  root partition: {config.root_partition}',
            f'  hostname: {config.hostname}',
            f'  username: {config.username}',
            f'  locale: {config.locale}',
            f'  timezone: {config.timezone}',
            f'  keyboard layout: {config.keyboard_layout}',
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
    finally:
        if state.config.execute and has_active_mounts(Path(state.config.target_mount)):
            try:
                cleanup(state)
            except subprocess.CalledProcessError as exc:
                print(f'[cleanup] best-effort cleanup failed: {exc}')


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
    elif phase == 'packages':
        install_packages(state)
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


def install_packages(state: State) -> None:
    config = state.config
    run_in_chroot(state, ['apt', 'update'], phase='apt-update')
    packages = ['linux-image-amd64', 'systemd-sysv', *PACKAGE_PROFILES[config.package_profile]]
    run_in_chroot(state, ['apt', 'install', '-y', *packages], phase='install-packages')


def configure_system(state: State) -> None:
    config = state.config
    hostname = shlex.quote(config.hostname)
    locale = shlex.quote(config.locale)
    hosts_content = '\n'.join(['127.0.0.1 localhost', f'127.0.1.1 {config.hostname}'])
    keyboard_content = '\n'.join([
        'XKBMODEL="pc105"',
        f'XKBLAYOUT={config.keyboard_layout}',
        'XKBVARIANT=""',
        'XKBOPTIONS=""',
        'BACKSPACE="guess"',
    ])
    run_in_chroot(state, ['bash', '-lc', f"printf '%s\\n' {hostname} > /etc/hostname"], phase='hostname')
    run_in_chroot(state, ['bash', '-lc', f"cat > /etc/hosts <<'EOF'\n{hosts_content}\nEOF"], phase='hosts')
    run_in_chroot(state, ['bash', '-lc', f"printf '%s UTF-8\\n' {shlex.quote(config.locale)} > /etc/locale.gen && locale-gen && update-locale LANG={shlex.quote(config.locale)}"], phase='locale')
    run_in_chroot(state, ['ln', '-sf', f'/usr/share/zoneinfo/{config.timezone}', '/etc/localtime'], phase='timezone')
    run_in_chroot(state, ['dpkg-reconfigure', '-f', 'noninteractive', 'tzdata'], phase='timezone')
    run_in_chroot(state, ['bash', '-lc', f"cat > /etc/default/keyboard <<'EOF'\n{keyboard_content}\nEOF"], phase='keyboard')
    run_in_chroot(state, ['dpkg-reconfigure', '-f', 'noninteractive', 'keyboard-configuration'], phase='keyboard')
    if config.package_profile == 'standard-tty':
        run_in_chroot(state, ['systemctl', 'enable', 'NetworkManager'], phase='services')
        run_in_chroot(state, ['systemctl', 'enable', 'ssh'], phase='services')


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
    run_in_chroot(state, ['bash', '-lc', f"printf '%s:%s\\n' root {shlex.quote(config.root_password or '<unset>')} | chpasswd"], phase='root-password')
    run_in_chroot(state, ['bash', '-lc', f"printf '%s:%s\\n' {shlex.quote(config.username)} {shlex.quote(config.user_password or '<unset>')} | chpasswd"], phase='user-password')


def install_bootloader(state: State) -> None:
    run_in_chroot(state, ['apt', 'install', '-y', 'grub-efi-amd64'], phase='install-grub')
    run_in_chroot(state, ['grub-install', '--target=x86_64-efi', '--efi-directory=/boot/efi', '--bootloader-id=debian', '--removable'], phase='grub-install')
    run_in_chroot(state, ['update-grub'], phase='grub-config')


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


def run_in_chroot(state: State, command: list[str], *, phase: str) -> None:
    run_command(['chroot', state.config.target_mount, *command], phase=phase, state=state)


def run_command(command: list[str], *, phase: str, state: State, input_text: str | None = None) -> None:
    line = f'[{phase}] {shlex.join(command)}'
    append_log(state.config, line)
    print(line)
    if not state.config.execute:
        return
    subprocess.run(command, input=input_text, text=True, check=True)


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
