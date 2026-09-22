# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ASCOS

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import threading
import time

import frida

def base_directory() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


AGENT_PATH = os.path.join(base_directory(), "agent.js")
ASSETS_DIR = os.path.join(base_directory(), "assets")
VERSION = "1.0.0"


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


class TimeShiftSession:
    def __init__(self, pid, session, script):
        self.pid = pid
        self.session = session
        self.script = script
        self._detached = threading.Event()
        session.on("detached", self._handle_detached)

    def _handle_detached(self, *args):
        self._detached.set()

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
    print("[timeshift] hedef kapandi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
