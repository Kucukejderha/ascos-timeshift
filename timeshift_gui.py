# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ASCOS

from __future__ import annotations

import datetime as dt
import os
import queue
import shlex
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import timeshift

MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 ASCOS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

NAVY = "#19304E"
NAVY_SECTION = "#91AACA"
NAVY_TEXT = "#BECFE4"
BLUE = "#2B6FB8"
BLUE_HOVER = "#2360A2"
CANVAS = "#F4F7FB"
BORDER = "#D2DCE8"
INK = "#1E2B3D"
MUTED = "#617187"
SUCCESS = "#69D5A4"
DANGER = "#D9534F"
NOTICE_BG = "#E8F1FB"
NOTICE_BORDER = "#BED5EE"
NOTICE_TEXT = "#2A5B8F"
LINK_HOVER = "#85BEF4"

FONT = ("Segoe UI", 9)
FONT_SEMI = ("Segoe UI Semibold", 9)
FONT_SMALL = ("Segoe UI Semibold", 8)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SIDEBAR_TITLE = ("Segoe UI Semibold", 17)
FONT_BRAND = ("Segoe UI Semibold", 15)
FONT_LINK = ("Segoe UI Semibold", 10)

WEBSITE_URL = "https://rotaniz.com/ascos-araclar/"


class TimeShiftGui:
    def __init__(self, root):
        self.root = root
        self.root.title("ASCOS TimeShift Yönetimi")
        self.root.configure(bg=CANVAS)
        self.root.geometry("1000x680")
        self.root.minsize(860, 620)
        self.messages = queue.Queue()
        self.session = None
        self._configure_styles()
        self._apply_window_icon()
        self._build_sidebar()
        self._build_workspace()
        self._fill_now()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_messages)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Secondary.TButton", background="white", foreground=INK,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        focuscolor="white", relief="solid", borderwidth=1,
                        padding=(12, 6), font=FONT)
        style.map("Secondary.TButton",
                  background=[("active", "#F9FBFD"), ("disabled", CANVAS)],
                  foreground=[("disabled", "#A9B4C4")])
        style.configure("Primary.TButton", background=BLUE, foreground="white",
                        bordercolor=BLUE, lightcolor=BLUE, darkcolor=BLUE,
                        focuscolor=BLUE, relief="solid", borderwidth=1,
                        padding=(14, 6), font=FONT_SEMI)
        style.map("Primary.TButton",
                  background=[("active", BLUE_HOVER), ("disabled", "#9DBBDC")],
                  foreground=[("disabled", "white")])
        style.configure("App.TEntry", fieldbackground="white", background="white",
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        insertcolor=INK, padding=5, relief="flat")
        style.map("App.TEntry",
                  bordercolor=[("focus", BLUE)], lightcolor=[("focus", BLUE)],
                  darkcolor=[("focus", BLUE)])
        style.configure("App.TCheckbutton", background="white", foreground=INK,
                        focuscolor="white")
        style.map("App.TCheckbutton", background=[("active", "white")])
        style.configure("App.Vertical.TScrollbar", background=CANVAS, troughcolor=CANVAS,
                        bordercolor=CANVAS, arrowcolor=MUTED)

    def _apply_window_icon(self):
        icon_path = os.path.join(timeshift.ASSETS_DIR, "ASCOS-TimeShift.ico")
        if os.path.isfile(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

    def _load_logo(self, size):
        if size == 52:
            path = os.path.join(timeshift.ASSETS_DIR, "ASCOS-TimeShift-52.png")
            if os.path.isfile(path):
                try:
                    return tk.PhotoImage(file=path)
                except tk.TclError:
                    return None
        path = os.path.join(timeshift.ASSETS_DIR, "ASCOS-TimeShift-128.png")
        if os.path.isfile(path):
            try:
                image = tk.PhotoImage(file=path)
                factor = max(1, round(128 / size))
                return image.subsample(factor, factor)
            except tk.TclError:
                return None
        return None

    def _build_sidebar(self):
        rail = tk.Frame(self.root, bg=NAVY, width=232)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        top = tk.Frame(rail, bg=NAVY)
        top.pack(fill="x", padx=22, pady=(28, 0))
        logo = self._load_logo(52)
        if logo is not None:
            logo_label = tk.Label(top, image=logo, bg=NAVY, bd=0)
            logo_label.image = logo
            logo_label.pack(side="left")
        else:
            tk.Label(top, text="A", fg="white", bg=BLUE, font=("Segoe UI Semibold", 18),
                     width=3, height=1).pack(side="left")
        tk.Label(top, text="ASCOS\nTimeShift", fg="white", bg=NAVY, font=FONT_BRAND,
                 justify="left", anchor="nw").pack(side="left", padx=(10, 0))

        tk.Label(rail, text="SANAL ZAMAN", fg=NAVY_SECTION, bg=NAVY, font=FONT_SMALL,
                 anchor="w").pack(fill="x", padx=22, pady=(34, 0))
        tk.Label(rail, text="Zaman\nkaydırma", fg="white", bg=NAVY, font=FONT_SIDEBAR_TITLE,
                 justify="left", anchor="w").pack(fill="x", padx=22, pady=(6, 0))
        tk.Label(rail, text="Bir uygulamayı seçilen\ntarih ve saatle başlatın;\nsistem saati değişmez.",
                 fg=NAVY_TEXT, bg=NAVY, font=FONT, justify="left", anchor="w").pack(
            fill="x", padx=22, pady=(12, 0))

        bottom = tk.Frame(rail, bg=NAVY)
        bottom.pack(side="bottom", fill="x", padx=22, pady=(0, 22))
        tk.Label(bottom, text="ASCOS HAKKINDA", fg=NAVY_SECTION, bg=NAVY, font=FONT_SMALL,
                 anchor="w").pack(fill="x")
        website = tk.Label(bottom, text="rotaniz.com  ↗", fg="white", bg=NAVY,
                           font=FONT_LINK, anchor="w", cursor="hand2")
        website.pack(fill="x", pady=(4, 0))
        website.bind("<Button-1>", lambda event: self._open_website())
        about = tk.Label(bottom, text="Hakkında", fg=LINK_HOVER, bg=NAVY, font=FONT_SEMI,
                         anchor="w", cursor="hand2")
        about.pack(fill="x", pady=(2, 12))
        about.bind("<Button-1>", lambda event: self._show_about())

        status_row = tk.Frame(bottom, bg=NAVY)
        status_row.pack(fill="x")
        self.status_dot = tk.Canvas(status_row, width=10, height=10, bg=NAVY,
                                    highlightthickness=0)
        self.status_dot.pack(side="left")
        self.status_dot_id = self.status_dot.create_oval(1, 1, 9, 9, fill=SUCCESS, outline="")
        self.status_label = tk.Label(status_row, text="Hazır", fg=NAVY_TEXT, bg=NAVY,
                                     font=FONT, anchor="w")
        self.status_label.pack(side="left", padx=(6, 0))

    def _build_workspace(self):
        work = tk.Frame(self.root, bg=CANVAS)
        work.pack(side="left", fill="both", expand=True)

        heading = tk.Frame(work, bg=CANVAS)
        heading.pack(fill="x", padx=28, pady=(24, 0))
        tk.Label(heading, text="Sanal saat ile başlat", fg=INK, bg=CANVAS, font=FONT_TITLE,
                 anchor="w").pack(fill="x")
        tk.Label(heading, text="Uygulamayı seçin, tarih ve saati belirleyin; sistem saatiniz değişmez.",
                 fg=MUTED, bg=CANVAS, font=FONT, anchor="w").pack(fill="x", pady=(4, 0))

        notice = tk.Frame(work, bg=NOTICE_BG, highlightthickness=1,
                          highlightbackground=NOTICE_BORDER)
        notice.pack(fill="x", padx=28, pady=(16, 14))
        icon = tk.Canvas(notice, width=16, height=16, bg=NOTICE_BG, highlightthickness=0)
        icon.pack(side="left", padx=(14, 8), pady=10)
        icon.create_oval(2, 2, 14, 14, outline=NOTICE_TEXT, width=1)
        icon.create_text(8, 8, text="i", fill=NOTICE_TEXT, font=("Segoe UI Semibold", 8))
        tk.Label(notice, text="Hedef program seçilen tarih ve saatle başlatılır; diğer uygulamalar etkilenmez.",
                 fg=NOTICE_TEXT, bg=NOTICE_BG, font=FONT, anchor="w").pack(side="left", pady=10)

        form = tk.Frame(work, bg="white", highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="x", padx=28)
        inner = tk.Frame(form, bg="white")
        inner.pack(fill="x", padx=16, pady=14)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(2, weight=0)

        tk.Label(inner, text="UYGULAMA", fg=MUTED, bg="white", font=FONT_SMALL,
                 anchor="w").grid(row=0, column=0, columnspan=3, sticky="w")
        self.exe_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self.exe_var, style="App.TEntry").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(3, 10))
        ttk.Button(inner, text="Gözat…", style="Secondary.TButton",
                   command=self._browse).grid(row=1, column=2, sticky="e", padx=(8, 0), pady=(3, 10))

        tk.Label(inner, text="TARİH (YYYY-AA-GG)", fg=MUTED, bg="white", font=FONT_SMALL,
                 anchor="w").grid(row=2, column=0, sticky="w")
        tk.Label(inner, text="SAAT (SS:DD:SS)", fg=MUTED, bg="white", font=FONT_SMALL,
                 anchor="w").grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.date_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self.date_var, style="App.TEntry").grid(
            row=3, column=0, sticky="ew", pady=(3, 10))
        self.time_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self.time_var, style="App.TEntry").grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(3, 10))
        ttk.Button(inner, text="Şu an", style="Secondary.TButton",
                   command=self._fill_now).grid(row=3, column=2, sticky="e", padx=(8, 0), pady=(3, 10))

        tk.Label(inner, text="ARGÜMANLAR (isteğe bağlı)", fg=MUTED, bg="white",
                 font=FONT_SMALL, anchor="w").grid(row=4, column=0, columnspan=3, sticky="w")
        self.args_var = tk.StringVar()
        ttk.Entry(inner, textvariable=self.args_var, style="App.TEntry").grid(
            row=5, column=0, columnspan=3, sticky="ew", pady=(3, 10))

        options = tk.Frame(inner, bg="white")
        options.grid(row=6, column=0, columnspan=3, sticky="w")
        self.freeze_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Saat donuk kalsın (freeze)", variable=self.freeze_var,
                        style="App.TCheckbutton").pack(side="left")
        self.ticks_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Tick sayaçlarını da kaydır", variable=self.ticks_var,
                        style="App.TCheckbutton").pack(side="left", padx=(16, 0))
        self.early_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Erken enjeksiyon", variable=self.early_var,
                        style="App.TCheckbutton").pack(side="left", padx=(16, 0))

        tk.Label(work, text="GÜNLÜK", fg=MUTED, bg=CANVAS, font=FONT_SMALL,
                 anchor="w").pack(fill="x", padx=28, pady=(14, 4))
        log_frame = tk.Frame(work, bg="white", highlightthickness=1,
                             highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True, padx=28)
        self.log_text = tk.Text(log_frame, bg="white", fg=INK, bd=0, highlightthickness=0,
                                font=FONT, wrap="word", padx=10, pady=8, height=6,
                                state="disabled")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview,
                                  style="App.Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        footer = tk.Frame(work, bg=CANVAS)
        footer.pack(fill="x", padx=28, pady=(12, 20))
        self.workspace_status = tk.Label(footer, text="Hazır", fg=MUTED, bg=CANVAS,
                                         font=FONT, anchor="w")
        self.workspace_status.pack(side="left")
        self.start_button = ttk.Button(footer, text="Başlat", style="Primary.TButton",
                                       command=self._start)
        self.start_button.pack(side="right")
        self.stop_button = ttk.Button(footer, text="Durdur", style="Secondary.TButton",
                                      command=self._stop, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 8))

    def _set_status(self, text, kind="idle"):
        colors = {"idle": MUTED, "running": SUCCESS, "error": DANGER}
        dot_colors = {"idle": MUTED, "running": SUCCESS, "error": DANGER}
        self.status_label.configure(text=text)
        self.workspace_status.configure(text=text, fg=colors.get(kind, MUTED))
        self.status_dot.itemconfigure(self.status_dot_id, fill=dot_colors.get(kind, MUTED))

    def _open_website(self):
        try:
            webbrowser.open(WEBSITE_URL)
        except Exception as exc:
            messagebox.showwarning("ASCOS TimeShift", f"Web sitesi açılamadı.\n\n{exc}")

    def _fill_now(self):
        now = dt.datetime.now()
        self.date_var.set(now.strftime("%Y-%m-%d"))
        self.time_var.set(now.strftime("%H:%M:%S"))

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Uygulama seç",
            filetypes=[("Uygulamalar", "*.exe"), ("Tüm dosyalar", "*.*")],
        )
        if path:
            self.exe_var.set(path)

    def _find_license_path(self):
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "LICENSE"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "LICENSE"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _license_text(self):
        path = self._find_license_path()
        if path is not None:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except OSError:
                pass
        return MIT_LICENSE_TEXT

    def _open_license(self):
        path = self._find_license_path()
        if path is None:
            messagebox.showinfo("ASCOS TimeShift", "Lisans dosyası bulunamadı.")
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("ASCOS TimeShift", f"Lisans dosyası açılamadı: {exc}")

    def _show_about(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Hakkında")
        dialog.configure(bg="white")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        header = tk.Frame(dialog, bg=NAVY)
        header.pack(fill="x")
        logo = self._load_logo(40)
        if logo is not None:
            logo_label = tk.Label(header, image=logo, bg=NAVY, bd=0)
            logo_label.image = logo
            logo_label.pack(side="left", padx=(16, 10), pady=12)
        tk.Label(header, text="ASCOS TimeShift", fg="white", bg=NAVY,
                 font=("Segoe UI Semibold", 13)).pack(side="left", pady=12)

        body = tk.Frame(dialog, bg="white")
        body.pack(fill="both", expand=True, padx=16, pady=12)
        tk.Label(body, text=f"Sürüm {timeshift.VERSION}", fg=INK, bg="white",
                 font=FONT_SEMI, anchor="w").pack(fill="x")
        tk.Label(body, text="Copyright (c) 2026 ASCOS", fg=MUTED, bg="white",
                 font=FONT, anchor="w").pack(fill="x", pady=(2, 0))
        tk.Label(body, text="MIT lisansı ile açık kaynak olarak yayımlanmıştır.",
                 fg=MUTED, bg="white", font=FONT, anchor="w").pack(fill="x", pady=(2, 8))

        license_frame = tk.Frame(body, bg="white", highlightthickness=1,
                                 highlightbackground=BORDER)
        license_frame.pack(fill="both", expand=True)
        text = tk.Text(license_frame, width=66, height=13, wrap="word", bg="white",
                       fg=INK, bd=0, highlightthickness=0, font=FONT, padx=10, pady=8)
        text.insert("1.0", self._license_text())
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)

        buttons = tk.Frame(body, bg="white")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Lisans dosyasını aç", style="Secondary.TButton",
                   command=self._open_license).pack(side="left")
        ttk.Button(buttons, text="Kapat", style="Primary.TButton",
                   command=dialog.destroy).pack(side="right")

        try:
            dialog.grab_set()
        except tk.TclError:
            pass

    def _start(self):
        if self.session is not None:
            return
        executable = self.exe_var.get().strip().strip('"')
        if not executable:
            messagebox.showwarning("ASCOS TimeShift", "Önce bir uygulama seçin.")
            return
        if not os.path.isfile(executable):
            messagebox.showerror("ASCOS TimeShift", "Uygulama dosyası bulunamadı:\n" + executable)
            return
        try:
            when = timeshift.parse_datetime(self.date_var.get(), self.time_var.get())
        except timeshift.TimeShiftError as exc:
            messagebox.showerror("ASCOS TimeShift", str(exc))
            return
        try:
            target_args = [item.strip('"') for item in shlex.split(self.args_var.get(), posix=False)]
        except ValueError as exc:
            messagebox.showerror("ASCOS TimeShift", "Argümanlar ayrıştırılamadı: " + str(exc))
            return

        self._set_running(True)
        self._set_status("Hedef başlatılıyor…", "idle")
        self._append_log("Başlatılıyor: " + executable)
        worker = threading.Thread(
            target=self._run,
            args=(executable, target_args, when, self.freeze_var.get(), self.ticks_var.get(),
                  self.early_var.get()),
            daemon=True,
        )
        worker.start()

    def _run(self, executable, target_args, when, freeze, ticks, early):
        try:
            self.session = timeshift.launch(
                executable,
                target_args=target_args,
                when=when,
                freeze=freeze,
                ticks=ticks,
                early_attach=early,
                on_log=lambda message: self.messages.put(("log", message)),
                on_error=lambda message: self.messages.put(("log", "HATA: " + message)),
            )
            self.messages.put(("log", f"Hedef başlatıldı (pid {self.session.pid})."))
            self.messages.put(("status", ("Hedef çalışıyor (pid %d)" % self.session.pid, "running")))
            self.session.wait()
            self.messages.put(("log", "Hedef kapandı."))
            self.messages.put(("status", ("Hazır", "idle")))
        except timeshift.TimeShiftError as exc:
            self.messages.put(("log", "HATA: " + str(exc)))
            self.messages.put(("status", ("Hata", "error")))
        except Exception as exc:
            self.messages.put(("log", f"Beklenmeyen hata: {exc}"))
            self.messages.put(("status", ("Hata", "error")))
        finally:
            self.session = None
            self.messages.put(("done", ""))

    def _stop(self):
        session = self.session
        if session is not None:
            session.stop()

    def _set_running(self, running):
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_messages(self):
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(payload)
            elif kind == "status":
                text, state = payload
                self._set_status(text, state)
            elif kind == "done":
                self._set_running(False)
        self.root.after(100, self._drain_messages)

    def _on_close(self):
        if self.session is not None and self.session.is_running():
            if not messagebox.askyesno("ASCOS TimeShift", "Hedef uygulama hâlâ çalışıyor. Kapatılsın mı?"):
                return
            self.session.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    TimeShiftGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
