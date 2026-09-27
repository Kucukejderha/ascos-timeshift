# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ASCOS
"""ASCOS ortak tanılama ve günlük istemcisi.

Kullanım:
    from ascos_logging import Diagnostics, Settings

    settings = Settings(config_dir, defaults={"upload_url": "...", "api_key": "..."})
    diag = Diagnostics(app="timeshift", version="1.1.0", config_dir=config_dir, settings=settings)
    diag.set_run_context(mode="late", freeze=False)
    diag.set_target(path=..., arch=..., fileVersion=...)
    diag.log("hook: GetSystemTime")
    diag.finish(exit_code=0xC0000005, detach_reason="process-crashed")
    payload = diag.build_payload()
    path = diag.save_local(payload)
    ok, detail = diag.upload(payload)
"""

from __future__ import annotations

import ctypes
import gzip
import json
import os
import platform
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

__version__ = "0.1.0"
SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 15

ISRG_ROOT_X1_PEM = """-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAwTzELMAkGA1UE
BhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2VhcmNoIEdyb3VwMRUwEwYDVQQD
EwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQG
EwJVUzEpMCcGA1UEChMgSW50ZXJuZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMT
DElTUkcgUm9vdCBYMTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54r
Vygch77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+0TM8ukj1
3Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6UA5/TR5d8mUgjU+g4rk8K
b4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sWT8KOEUt+zwvo/7V3LvSye0rgTBIlDHCN
Aymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyHB5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ
4Q7e2RCOFvu396j3x+UCB5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf
1b0SHzUvKBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWnOlFu
hjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTnjh8BCNAw1FtxNrQH
usEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbwqHyGO0aoSCqI3Haadr8faqU9GY/r
OPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CIrU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4G
A1UdDwEB/wQEAwIBBjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY
9umbbjANBgkqhkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ3BebYhtF8GaV
0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KKNFtY2PwByVS5uCbMiogziUwt
hDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJw
TdwJx4nLCgdNbOhdjsnvzqvHu7UrTkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nx
e5AW0wdeRlN8NwdCjNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZA
JzVcoyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq4RgqsahD
YVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPAmRGunUHBcnWEvgJBQl9n
JEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57demyPxgcYxn/eR44/KJ4EBs+lVDR3veyJ
m+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
"""


def _ssl_contexts():
    contexts = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        pass
    try:
        bundle = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bundle.load_verify_locations(cadata=ISRG_ROOT_X1_PEM)
        bundle.check_hostname = True
        contexts.append(bundle)
    except Exception:
        pass
    return contexts


def _is_certificate_error(exc):
    if isinstance(exc, ssl.SSLError):
        return True
    return isinstance(getattr(exc, "reason", None), ssl.SSLError)


def _open_with_fallback(request, timeout):
    last_error = None
    for context in _ssl_contexts():
        try:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
            return opener.open(request, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except Exception as exc:
            last_error = exc
            if not _is_certificate_error(exc):
                raise
    if last_error is not None:
        raise last_error
    return urllib.request.urlopen(request, timeout=timeout)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _replace_all(value, replacements):
    if isinstance(value, str):
        for source, target in replacements:
            if source:
                value = value.replace(source, target)
        return value
    if isinstance(value, dict):
        return {key: _replace_all(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_all(item, replacements) for item in value]
    return value


class Settings:
    def __init__(self, config_dir, defaults=None):
        self.config_dir = config_dir
        self.path = os.path.join(config_dir, "settings.json")
        self.data = {
            "upload_url": "",
            "api_key": "",
            "anonymize": True,
            "ask_before_upload": True,
            "keep_logs": 20,
        }
        if defaults:
            self.data.update(defaults)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError):
            pass
        return self

    def save(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return self

    def ensure_defaults(self, defaults):
        changed = False
        for key, value in defaults.items():
            if not self.data.get(key):
                self.data[key] = value
                changed = True
        if changed:
            self.save()
        return changed

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def upload_url(self):
        return str(self.data.get("upload_url") or "").rstrip("/")

    @property
    def api_key(self):
        return str(self.data.get("api_key") or "")

    @property
    def anonymize(self):
        return bool(self.data.get("anonymize", True))

    @property
    def ask_before_upload(self):
        return bool(self.data.get("ask_before_upload", True))

    @property
    def keep_logs(self):
        try:
            return int(self.data.get("keep_logs", 20) or 0)
        except (TypeError, ValueError):
            return 20


class Diagnostics:
    def __init__(self, app, version, config_dir, settings=None):
        self.app = app
        self.version = version
        self.config_dir = config_dir
        self.logs_dir = os.path.join(config_dir, "logs")
        self.settings = settings or Settings(config_dir)
        self.started_at = time.time()
        self.ended_at = None
        self.events = []
        self.context = {}
        self.result = {}
        self.children = {}

    def log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{stamp}] {message}")

    def set_run_context(self, **values):
        self.context.setdefault("runContext", {}).update(values)

    def set_target(self, **values):
        self.context.setdefault("target", {}).update(values)

    def set_data(self, **values):
        self.context.setdefault("data", {}).update(values)

    def set_event(self, event_type, summary, severity="error"):
        self.context["eventType"] = event_type
        self.context["summary"] = summary
        self.context["severity"] = severity

    def add_child(self, pid, name):
        try:
            self.children[int(pid)] = str(name)
        except (TypeError, ValueError):
            pass

    def finish(self, exit_code=None, detach_reason=None, crash=None):
        self.ended_at = time.time()
        duration_ms = int((self.ended_at - self.started_at) * 1000)
        result = {
            "durationMs": duration_ms,
            "exitCode": exit_code,
            "exitCodeHex": None if exit_code is None else f"0x{exit_code & 0xFFFFFFFF:08X}",
            "detachReason": detach_reason,
        }
        if crash:
            result["crash"] = str(crash)
        self.result = result
        return duration_ms

    def is_failure(self, quick_exit_ms=3000):
        if self.result.get("detachReason") == "process-crashed":
            return True
        if self.result.get("crash"):
            return True
        code = self.result.get("exitCode")
        if code is None:
            return bool(self.context.get("failedToLaunch"))
        if code != 0:
            return True
        duration = int(self.result.get("durationMs") or 0)
        return 0 < duration < quick_exit_ms

    def build_payload(self, anonymize=None):
        if anonymize is None:
            anonymize = self.settings.anonymize
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "app": self.app,
            "appVersion": self.version,
            "timestampUtc": _now_iso(),
            "severity": self.context.get("severity") or ("error" if self.result else "info"),
            "eventType": self.context.get("eventType") or "session",
            "summary": self.context.get("summary") or "",
            "os": self._os_info(),
            "userMasked": "%USER%",
            "runContext": self.context.get("runContext", {}),
            "target": self.context.get("target", {}),
            "result": self.result,
            "children": [
                {"pid": pid, "name": name} for pid, name in sorted(self.children.items())
            ],
            "data": self.context.get("data", {}),
            "logText": "\n".join(self.events),
        }
        if anonymize:
            payload = _replace_all(payload, self._anonymize_rules())
        return payload

    def _anonymize_rules(self):
        rules = []
        username = os.environ.get("USERNAME") or os.environ.get("USER")
        profile = os.environ.get("USERPROFILE") or ""
        if profile:
            rules.append((profile, "%USERPROFILE%"))
        if username:
            rules.append((username, "%USER%"))
        return rules

    def _os_info(self):
        info = {
            "platform": platform.platform(),
            "version": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
        }
        try:
            info["windowsBuild"] = sys.getwindowsversion().build
        except Exception:
            pass
        try:
            info["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass
        return info

    def save_local(self, payload=None):
        payload = payload if payload is not None else self.build_payload()
        try:
            os.makedirs(self.logs_dir, exist_ok=True)
        except OSError:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = f"-{int(self.started_at * 1000) % 1000:03d}"
        path = os.path.join(self.logs_dir, f"{self.app}-{stamp}{suffix}.json")
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError:
            return None
        self._rotate()
        return path

    def _rotate(self):
        keep = self.settings.keep_logs
        if keep <= 0:
            return
        try:
            files = []
            for name in os.listdir(self.logs_dir):
                if name.endswith(".json"):
                    path = os.path.join(self.logs_dir, name)
                    try:
                        files.append((os.path.getmtime(path), path))
                    except OSError:
                        pass
            files.sort(reverse=True)
            for _, path in files[keep:]:
                try:
                    os.remove(path)
                except OSError:
                    pass
        except OSError:
            pass

    def upload(self, payload=None, timeout=DEFAULT_TIMEOUT):
        url = self.settings.upload_url
        key = self.settings.api_key
        if not url:
            return False, "yükleme adresi tanımlı değil"
        if not key:
            return False, "API anahtarı tanımlı değil"
        payload = payload if payload is not None else self.build_payload()
        body = gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        request = urllib.request.Request(url + "/upload", data=body, method="POST")
        request.add_header("Content-Type", "application/json; charset=utf-8")
        request.add_header("Content-Encoding", "gzip")
        request.add_header("X-ASCOS-Key", key)
        request.add_header("User-Agent", f"ascos-logging/{__version__} ({self.app}/{self.version})")
        try:
            with _open_with_fallback(request, timeout) as response:
                text = response.read().decode("utf-8", "replace")
            data = json.loads(text) if text else {}
            if data.get("ok"):
                return True, str(data.get("id") or "")
            return False, text or "bilinmeyen hata"
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")
            except Exception:
                detail = str(exc)
            return False, f"HTTP {exc.code}: {detail}"
        except Exception as exc:
            return False, str(exc)


def preview_text(payload, limit=4000):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > limit:
        text = text[:limit] + "\n... (kısaltıldı)"
    return text
