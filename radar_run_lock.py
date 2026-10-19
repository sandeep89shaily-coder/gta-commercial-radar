"""Cross-platform, process-owned lock for GTA Radar's collector + AI pipeline.

The old V6_RUNNING.lock was only a marker file, and a crashed process could
leave it forever. A separate operating-system byte-range lock is now held for
the entire run. The legacy marker is retained only for compatibility with
older installers, and automatically recovered when its owner has exited.

No active lock is ever removed based solely on age. Do not use this component
on network shares with unsupported or unreliable native file locking.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import time
import uuid


class ActiveRadarRun(RuntimeError):
    """Another instance is running, or the old marker cannot be verified."""


def _acquire_os_lock(file):
    try:
        if os.name == "nt":
            import msvcrt
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise ActiveRadarRun(
            "Another GTA Radar run is currently using the database. "
            "Do not start a second run while it is active."
        ) from exc


def _release_os_lock(file):
    try:
        if os.name == "nt":
            import msvcrt
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    finally:
        file.close()


def _windows_process_alive(pid, marker_mtime):
    """True for the SAME running process; False for dead/reused PID; None if unknown."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetExitCodeProcess.restype = wintypes.BOOL
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(FileTime)] * 4
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        err = ctypes.get_last_error()
        if err in (87, 1168):  # Invalid ID or process doesn't exist
            return False
        return None  # Access denied or other uncertainty: never force a deletion.

    try:
        exit_code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        if exit_code.value != 259:  # STILL_ACTIVE
            return False
        created = FileTime()
        exited, kernel, user = FileTime(), FileTime(), FileTime()
        if not k32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
        creation_epoch = (((created.high << 32) | created.low) / 10_000_000
                          - 11_644_473_600)
        # If the process was created AFTER this marker, Windows reused the PID.
        return creation_epoch <= marker_mtime + 3
    finally:
        k32.CloseHandle(handle)


def _posix_process_alive(pid, marker_mtime):
    try:
        os.kill(pid, 0)  # Unix-only signal-zero liveness check, sends no signal.
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    except OSError:
        return None

    # Check the start time on Linux to avoid mistaking a reused PID for the
    # original owner. Other POSIX platforms fall back to liveness alone.
    try:
        proc = Path("/proc") / str(pid) / "stat"
        if proc.exists():
            fields = proc.read_text(encoding="ascii").rsplit(")", 1)[1].split()
            start_ticks = int(fields[19])  # proc stat field 22
            btime_line = next(line for line in Path("/proc/stat").read_text(
                encoding="ascii").splitlines() if line.startswith("btime "))
            creation_epoch = int(btime_line.split()[1]) + start_ticks / os.sysconf("SC_CLK_TCK")
            if creation_epoch > marker_mtime + 3:
                return False
    except (OSError, ValueError, IndexError, StopIteration):
        pass
    return True


def _process_alive(pid, marker_mtime):
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        return _windows_process_alive(pid, marker_mtime)
    return _posix_process_alive(pid, marker_mtime)


class RunLock:
    def __init__(self, handle, marker, identity):
        self._handle = handle
        self.marker = marker
        self.identity = identity

    def release(self):
        if self._handle is None:
            return
        try:
            # Do not erase someone else's marker if it has been replaced.
            if self.marker.exists():
                lines = self.marker.read_text(encoding="utf-8").splitlines()
                if len(lines) >= 3 and lines[2] == self.identity:
                    self.marker.unlink(missing_ok=True)
        finally:
            handle = self._handle
            self._handle = None
            _release_os_lock(handle)

    def unlink(self, missing_ok=True):
        """Compatibility with existing pipeline finally block and older tests."""
        self.release()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release()


def once_lock(results, stale_hours=None):
    """Acquire ownership safely; recover only proven-abandoned legacy markers.

    The .oslock byte-range lock releases automatically if Python crashes.
    The old .lock marker remains for compatibility with older scheduled V6
    instances, but a dead owner is removed immediately, not after 16 hours.
    """
    root = Path(results)
    root.mkdir(parents=True, exist_ok=True)
    kernel_path = root / "V6_PROCESS.oslock"
    marker = root / "V6_RUNNING.lock"
    handle = kernel_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        _acquire_os_lock(handle)
        if marker.exists():
            stat = marker.stat()
            try:
                lines = marker.read_text(encoding="utf-8").splitlines()
                owner = int(lines[0])
            except (OSError, ValueError, IndexError):
                owner = None

            if owner is None:
                # Can't confirm an active legacy owner. Give a recently created
                # unreadable marker time to clear before safe recovery.
                if time.time() - stat.st_mtime < 4 * 3600:
                    raise ActiveRadarRun(
                        "An existing Radar marker is unreadable and recent. "
                        "Please check for another scheduled Radar run."
                    )
            else:
                running = _process_alive(owner, stat.st_mtime)
                if running is not False:
                    raise ActiveRadarRun(
                        "Another GTA Radar process may still be running. "
                        "An active or unverifiable run will not be interrupted."
                    )
            marker.unlink(missing_ok=True)

        identity = uuid.uuid4().hex
        with marker.open("x", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\n"
                         + dt.datetime.now(dt.timezone.utc).isoformat() + "\n"
                         + identity + "\n")
        return RunLock(handle, marker, identity)
    except Exception:
        _release_os_lock(handle)
        raise
