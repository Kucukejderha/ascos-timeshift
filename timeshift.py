# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ASCOS

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import os
import struct
import sys
import threading
import time
from ctypes import wintypes

import frida


def base_directory() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


AGENT_PATH = os.path.join(base_directory(), "agent.js")
ASSETS_DIR = os.path.join(base_directory(), "assets")
CONFIG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ASCOS TimeShift")
VERSION = "1.1.0"

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
_version = ctypes.WinDLL("version", use_last_error=True) if os.name == "nt" else None


class TimeShiftError(Exception):
    pass


def load_agent_source() -> str:
    try:
        with open(AGENT_PATH, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise TimeShiftError(f"agent.js okunamadi: {exc}") from exc


def parse_datetime(date_text: str, time_text: str) -> dt.datetime:
    combined = f"{date_text.strip()} {time_text.strip()}"
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(combined, pattern)
        except ValueError:
            continue
    raise TimeShiftError("Tarih/saat formati gecersiz. Ornek: --date 2020-06-15 --time 12:30:00")


def open_exit_handle(pid):
    if _kernel32 is None:
        return None
    try:
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    except Exception:
        return None
    return handle or None


def query_exit_code(handle):
    if _kernel32 is None or not handle:
        return None
    code = wintypes.DWORD(0)
    if _kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
        return int(code.value)
    return None


def close_handle(handle):
    if _kernel32 is not None and handle:
        try:
            _kernel32.CloseHandle(handle)
        except Exception:
            pass


class _ProcessEntry32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def list_processes():
    if _kernel32 is None:
        return []
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return []
    try:
        entry = _ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(_ProcessEntry32W)
        processes = []
        if _kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                processes.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID),
                                  str(entry.szExeFile)))
                if not _kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
        return processes
    except Exception:
        return []
    finally:
        try:
            _kernel32.CloseHandle(snapshot)
        except Exception:
            pass


def sha256_file(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _file_version_info(path):
    if _version is None:
        return {}
    try:
        size = _version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return {}
        buffer = ctypes.create_string_buffer(size)
        if not _version.GetFileVersionInfoW(path, 0, size, buffer):
            return {}
        pointer = ctypes.c_void_p()
        length = wintypes.UINT()
        if not _version.VerQueryValueW(buffer, "\\VarFileInfo\\Translation",
                                       ctypes.byref(pointer), ctypes.byref(length)):
            return {}
        if length.value < 4:
            return {}
        lang, codepage = struct.unpack("<HH", ctypes.string_at(pointer, 4))
        result = {}
        fields = (
            ("FileVersion", "fileVersion"),
            ("ProductVersion", "productVersion"),
            ("ProductName", "productName"),
            ("CompanyName", "companyName"),
            ("FileDescription", "fileDescription"),
        )
        for key, name in fields:
            sub = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\{key}"
            if _version.VerQueryValueW(buffer, sub, ctypes.byref(pointer), ctypes.byref(length)):
                if length.value:
                    result[name] = ctypes.wstring_at(pointer, length.value).rstrip("\x00")
        return result
    except Exception:
        return {}


def describe_target(path):
    info = {"path": path}
    try:
        info["size"] = os.stat(path).st_size
    except OSError:
        pass
    try:
        with open(path, "rb") as handle:
            header = handle.read(0x400)
        if header[:2] == b"MZ":
            offset = int.from_bytes(header[0x3C:0x40], "little")
            machine = int.from_bytes(header[offset + 4:offset + 6], "little")
            info["arch"] = {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}.get(
                machine, f"0x{machine:04X}")
    except (OSError, ValueError, IndexError):
        pass
    try:
        info["sha256"] = sha256_file(path)
    except OSError:
        pass
    info.update(_file_version_info(path))
    return info


class TimeShiftSession:
    def __init__(self, pid, session, script):
        self.pid = pid
        self.session = session
        self.script = script
        self.exit_code = None
        self.detach_reason = None
        self.crash = None
        self.children = {}
        self.started_at = time.time()
        self.ended_at = None
        self._detached = threading.Event()
        self._stop_tracker = threading.Event()
        self._exit_handle = open_exit_handle(pid)
        session.on("detached", self._handle_detached)
        self._tracker = threading.Thread(target=self._track_children, daemon=True)
        self._tracker.start()

    def _handle_detached(self, reason=None, crash=None):
        if reason is not None:
            self.detach_reason = str(reason)
        if crash is not None:
            self.crash = str(crash)
        self.ended_at = time.time()
        self.exit_code = query_exit_code(self._exit_handle)
        close_handle(self._exit_handle)
        self._exit_handle = None
        self._stop_tracker.set()
        self._detached.set()

    def _track_children(self):
        while not self._stop_tracker.wait(1.5):
            processes = list_processes()
            if not processes:
                continue
            parents = {pid: ppid for pid, ppid, _ in processes}
            for pid, ppid, name in processes:
                if pid == self.pid:
                    continue
                current = ppid
                depth = 0
                while current and depth < 4:
                    if current == self.pid:
                        self.children[pid] = name
                        break
                    current = parents.get(current, 0)
                    depth += 1

    @property
    def duration_ms(self):
        end = self.ended_at or time.time()
        return int((end - self.started_at) * 1000)

    def wait(self):
        while not self._detached.wait(0.5):
            pass

    def is_running(self):
        return not self._detached.is_set()

    def stop(self):
        try:
            frida.kill(self.pid)
        except Exception:
            pass


def launch(executable, target_args=(), when=None, freeze=False, ticks=False,
           working_directory=None, early_attach=False, on_log=None, on_error=None):
    executable = os.path.abspath(executable)
    if not os.path.isfile(executable):
        raise TimeShiftError(f"Dosya bulunamadi: {executable}")

    when = when or dt.datetime.now()
    fake_utc_ms = round(when.timestamp() * 1000)
    argv = [executable, *target_args]
    cwd = working_directory or os.path.dirname(executable)

    emit_log = on_log or (lambda message: None)
    emit_error = on_error or emit_log

    try:
        pid = frida.spawn(argv, cwd=cwd)
    except frida.ExecutableNotFoundError as exc:
        raise TimeShiftError(f"Uygulama baslatilamadi (bulunamadi): {exc}") from exc
    except frida.PermissionDeniedError as exc:
        raise TimeShiftError(
            "Yetki reddedildi. Hedef yonetici haklari istiyorsa TimeShift'i de "
            "yonetici olarak calistirin."
        ) from exc
    except Exception as exc:
        raise TimeShiftError(f"Uygulama baslatilamadi: {exc}") from exc

    session = None
    script = None
    try:
        if early_attach:
            session = frida.attach(pid)
        else:
            frida.resume(pid)
            deadline = time.monotonic() + 4.0
            last_error = None
            while session is None:
                try:
                    session = frida.attach(pid)
                except Exception as exc:
                    last_error = exc
                    if time.monotonic() >= deadline:
                        raise TimeShiftError(
                            f"Hedefe baglanilamadi ({last_error}). Kisa omurlu uygulamalar icin "
                            "--early-attach kullanin."
                        ) from last_error
                    time.sleep(0.25)
        script = session.create_script(load_agent_source(), name="timeshift-agent")

        def handle_message(message, data):
            if message.get("type") == "send":
                payload = message.get("payload") or {}
                kind = payload.get("type")
                if kind == "log":
                    emit_log(str(payload.get("message", "")))
                elif kind == "error":
                    emit_error(str(payload.get("message", "")))
            elif message.get("type") == "error":
                emit_error(str(message.get("stack") or message.get("description") or "ajan hatasi"))

        script.on("message", handle_message)
        script.load()
        script.exports_sync.init({
            "fakeUtcMs": fake_utc_ms,
            "freeze": bool(freeze),
            "ticks": bool(ticks),
        })
        if early_attach:
            frida.resume(pid)
    except Exception as exc:
        try:
            frida.kill(pid)
        except Exception:
            pass
        if isinstance(exc, TimeShiftError):
            raise
        raise TimeShiftError(f"Enjeksiyon hatasi: {exc}") from exc

    return TimeShiftSession(pid, session, script)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="timeshift",
        description="Hedef uygulamayi sahte tarih/saat ile baslatir; sistem saati degismez.",
    )
    parser.add_argument("--date", required=True, help="Sahte tarih (YYYY-AA-GG)")
    parser.add_argument("--time", dest="time_text", required=True, help="Sahte saat (SS:DD:SS)")
    parser.add_argument("--freeze", action="store_true", help="Saat ilerlemesin, sabit kalsin")
    parser.add_argument("--ticks", action="store_true",
                        help="GetTickCount/GetTickCount64 degerlerini de kaydir")
    parser.add_argument("--cwd", default=None, help="Hedefin calisma dizini (varsayilan: exe klasoru)")
    parser.add_argument("--early-attach", action="store_true",
                        help="Hook'lari surec askidayken kur (hizli acilan uygulamalar icin)")
    parser.add_argument("--version", action="version", version=f"ASCOS TimeShift {VERSION}")
    parser.add_argument("target", help="Calistirilacak uygulama yolu")
    parser.add_argument("target_args", nargs=argparse.REMAINDER, help="Hedefe iletilecek argumanlar")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        when = parse_datetime(args.date, args.time_text)
        session = launch(
            args.target,
            target_args=args.target_args,
            when=when,
            freeze=args.freeze,
            ticks=args.ticks,
            working_directory=args.cwd,
            early_attach=args.early_attach,
            on_log=lambda message: print(f"[timeshift] {message}"),
            on_error=lambda message: print(f"[timeshift] HATA: {message}", file=sys.stderr),
        )
    except TimeShiftError as exc:
        print(f"[timeshift] HATA: {exc}", file=sys.stderr)
        return 1

    print(f"[timeshift] hedef calisiyor (pid {session.pid}). Cikmak icin Ctrl+C.")
    try:
        session.wait()
    except KeyboardInterrupt:
        session.stop()
    code = session.exit_code
    code_text = "bilinmiyor" if code is None else f"0x{code & 0xFFFFFFFF:08X}"
    print(f"[timeshift] hedef kapandi (cikis kodu: {code_text}, sure: {session.duration_ms} ms).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
