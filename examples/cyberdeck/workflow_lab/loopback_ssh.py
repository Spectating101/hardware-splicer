"""Ephemeral loopback OpenSSH + sandboxed shell for HS touchscreen tests.

This is deliberately NOT an SSH server to deploy to the Internet. It uses a
new host key, one new authorized key, strict pinned trust, localhost-only bind,
and a bwrap filesystem/network sandbox. The fixture and workspace disappear.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
import getpass
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import tempfile
import time


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True, text=True, timeout=15)


class LoopbackSSH(AbstractContextManager["LoopbackSSH"]):
    def __init__(self):
        self.temp: tempfile.TemporaryDirectory | None = None
        self.root: Path | None = None
        self.server: subprocess.Popen | None = None
        self.port: int | None = None

    def __enter__(self) -> "LoopbackSSH":
        try:
            for required in ("/usr/sbin/sshd", "ssh-keygen", "ssh", "bwrap", "tmux", "nano"):
                if shutil.which(required) is None:
                    raise RuntimeError(f"HS bench requires existing {required}; not fake SSH")
            # Interactive Ctrl-C requires the sandbox to retain a controlling
            # terminal. On Linux, that is acceptable for this local fixture
            # only when legacy TIOCSTI tty injection is disabled by the host.
            tiocsti=Path("/proc/sys/dev/tty/legacy_tiocsti")
            if not tiocsti.is_file() or tiocsti.read_text().strip()!="0":
                raise RuntimeError("interactive demo requires kernel TIOCSTI disabled; refusing unsafe PTY")
            self.temp = tempfile.TemporaryDirectory(prefix="hs-loopback-ssh-")
            self.root = Path(self.temp.name)
            os.chmod(self.root, 0o700)
            work = self.root / "work"
            work.mkdir(mode=0o700)
            _run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.root / "host")])
            _run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.root / "identity")])
            user = getpass.getuser()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                self.port = s.getsockname()[1]
            # Executing the SSH command is forcibly redirected to an isolated
            # workspace. No network routes, credentials, user HOME, GitHub
            # auth, source checkout or host writable paths are mounted.
            # /dev is synthetic; SSH PTY exists as already-open inherited fds.
            runner = self.root / "restricted_shell.sh"
            workspace = shlex.quote(str(work))
            runner.write_text(
                "#!/bin/sh\n"
                "exec /usr/bin/bwrap --die-with-parent --unshare-net --unshare-pid "
                "--ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib "
                "--ro-bind /lib64 /lib64 --dev /dev --proc /proc "
                "--tmpfs /tmp --dir /work --bind " + workspace + " /work "
                "--setenv HOME /work --setenv PATH /usr/bin:/bin "
                "--setenv TERM xterm-256color --setenv LC_ALL C.UTF-8 "
                "--chdir /work -- /bin/bash --noprofile --norc\n"
            )
            runner.chmod(0o700)
            public_key = (self.root / "identity.pub").read_text().strip()
            (self.root / "authorized_keys").write_text(
                f'command="{runner}",restrict,pty {public_key}\n'
            )
            (self.root / "authorized_keys").chmod(0o600)
            host_fields = (self.root / "host.pub").read_text().strip().split()
            (self.root / "known_hosts").write_text(
                f"[127.0.0.1]:{self.port} {host_fields[0]} {host_fields[1]}\n"
            )
            (self.root / "known_hosts").chmod(0o600)
            cfg = self.root / "sshd_config"
            cfg.write_text("\n".join([
                f"ListenAddress 127.0.0.1",
                f"Port {self.port}",
                f"HostKey {self.root/'host'}",
                f"PidFile {self.root/'sshd.pid'}",
                f"AuthorizedKeysFile {self.root/'authorized_keys'}",
                f"AllowUsers {user}",
                "AuthenticationMethods publickey",
                "PubkeyAuthentication yes",
                "PasswordAuthentication no",
                "KbdInteractiveAuthentication no",
                "UsePAM no",
                "StrictModes no",
                "PermitRootLogin no",
                "AllowTcpForwarding no",
                "AllowAgentForwarding no",
                "X11Forwarding no",
                "PermitTunnel no",
                "PermitUserEnvironment no",
                "PermitTTY yes",
                "PrintMotd no",
                "LogLevel ERROR",
                "MaxSessions 1",
                "MaxStartups 2:30:2",
                "Subsystem sftp internal-sftp",
                "",
            ]))
            _run(["/usr/sbin/sshd", "-t", "-f", str(cfg)])
            self.server = subprocess.Popen(
                ["/usr/sbin/sshd", "-D", "-e", "-f", str(cfg)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                start_new_session=True,
            )
            for _ in range(60):
                if self.server.poll() is not None:
                    raise RuntimeError("local sshd exited during startup: "+
                                       self.server.stderr.read().decode(errors="replace")[-500:])
                with socket.socket() as s:
                    s.settimeout(0.1)
                    if s.connect_ex(("127.0.0.1", self.port)) == 0:
                        break
                time.sleep(0.05)
            else:
                raise RuntimeError("loopback sshd didn't bind")
            return self
        except BaseException:
            self.close()
            raise

    def ssh_command(self, *, tty: bool = True, known_hosts: Path | None = None) -> list[str]:
        assert self.root is not None and self.port is not None
        return [
            "ssh", "-tt" if tty else "-T",
            "-i", str(self.root / "identity"),
            "-p", str(self.port),
            "-o", "StrictHostKeyChecking=yes",
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no",
            "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes",
            "-o", "ConnectTimeout=4",
            "-o", f"UserKnownHostsFile={known_hosts or self.root/'known_hosts'}",
            "-o", "GlobalKnownHostsFile=/dev/null",
            f"{getpass.getuser()}@127.0.0.1",
        ]

    def close(self) -> None:
        if self.server is not None:
            self.server.terminate()
            try:
                self.server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=3)
            self.server = None
        if self.temp is not None:
            self.temp.cleanup()
            self.temp = None

    def __exit__(self, *_exc) -> None:
        self.close()
