from __future__ import annotations

from pathlib import Path
import queue
import threading
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .analyzer import analyze_fontlib
from .charset_filter import filter_charset_by_font
from .errors import FontGenError
from .installer import (
    InstallConfig,
    install_replacement_fonts,
    restore_from_manifest,
    starsector_fonts_dir,
    validate_starsector_root,
)
from .rebuild_fontlib import RebuildConfig, rebuild_fontlib


APP_TITLE = "Starsector Font Replacer"
PACK_NAME = "Starsector Font Replacer"


class FontReplacerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x720")
        self.minsize(860, 620)
        self.log_queue: queue.Queue[str] = queue.Queue()

        self.starsector_root = tk.StringVar()
        self.target_font = tk.StringVar()
        self.source_font_dir = tk.StringVar()
        self.work_dir = tk.StringVar()
        self.atlas_size = tk.StringVar(value="4096")

        self.starsector_root.trace_add("write", self.on_root_changed)

        self.create_widgets()
        self.after(100, self.flush_log_queue)

    def create_widgets(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(8, weight=1)

        self.add_path_row(root, 0, "Starsector 根目录", self.starsector_root, self.pick_starsector_root)
        self.add_path_row(root, 1, "目标字体 TTF/OTF", self.target_font, self.pick_target_font)
        self.add_path_row(root, 2, "原字体库目录", self.source_font_dir, self.pick_source_font_dir)
        ttk.Label(
            root,
            text=(
                "提示：如果只想替换汉化字体包，请选择汉化字体库子集目录；"
                "如果选择整个 core fonts 目录，程序会尝试重建所有 .fnt。"
            ),
            foreground="#555555",
            wraplength=760,
        ).grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=(8, 8), pady=(0, 6))
        self.add_path_row(root, 4, "输出工作目录", self.work_dir, self.pick_work_dir)

        ttk.Label(root, text="Atlas size").grid(row=5, column=0, sticky=tk.W, pady=4)
        atlas = ttk.Combobox(
            root,
            textvariable=self.atlas_size,
            values=("2048", "4096"),
            width=12,
            state="readonly",
        )
        atlas.grid(row=5, column=1, sticky=tk.W, pady=4)

        buttons = ttk.Frame(root)
        buttons.grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=(12, 8))
        for index in range(6):
            buttons.columnconfigure(index, weight=1)

        ttk.Button(buttons, text="检查 Starsector 目录", command=self.check_starsector_dir).grid(row=0, column=0, padx=4, sticky=tk.EW)
        ttk.Button(buttons, text="分析当前字体库", command=self.analyze_fontlib_action).grid(row=0, column=1, padx=4, sticky=tk.EW)
        ttk.Button(buttons, text="过滤字符集", command=self.filter_charset_action).grid(row=0, column=2, padx=4, sticky=tk.EW)
        ttk.Button(buttons, text="生成替换字体", command=self.rebuild_fonts_action).grid(row=0, column=3, padx=4, sticky=tk.EW)
        ttk.Button(buttons, text="应用到游戏", command=self.install_action).grid(row=0, column=4, padx=4, sticky=tk.EW)
        ttk.Button(buttons, text="从备份还原", command=self.restore_action).grid(row=0, column=5, padx=4, sticky=tk.EW)

        ttk.Label(root, text="日志").grid(row=7, column=0, sticky=tk.W, pady=(10, 4))
        self.log_text = scrolledtext.ScrolledText(root, height=20, wrap=tk.WORD)
        self.log_text.grid(row=8, column=0, columnspan=3, sticky=tk.NSEW)

    def add_path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky=tk.EW, padx=(8, 8), pady=4)
        ttk.Button(parent, text="浏览...", command=command).grid(row=row, column=2, sticky=tk.E, pady=4)

    def on_root_changed(self, *_args) -> None:
        root = self.starsector_root.get().strip()
        if root:
            self.source_font_dir.set(str(starsector_fonts_dir(Path(root))))

    def pick_starsector_root(self) -> None:
        path = filedialog.askdirectory(title="选择 Starsector 根目录")
        if path:
            self.starsector_root.set(path)

    def pick_target_font(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 TTF/OTF 字体",
            filetypes=[("Font files", "*.ttf *.otf"), ("All files", "*.*")],
        )
        if path:
            self.target_font.set(path)

    def pick_source_font_dir(self) -> None:
        path = filedialog.askdirectory(title="选择 graphics/fonts 字体目录")
        if path:
            self.source_font_dir.set(path)

    def pick_work_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输出工作目录")
        if path:
            self.work_dir.set(path)

    def check_starsector_dir(self) -> None:
        command = "check_starsector_dir"
        try:
            fonts_dir = validate_starsector_root(self.require_path(self.starsector_root, "Starsector 根目录"))
        except FontGenError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            self.log(f"检查失败: {exc}")
            self.append_full_log(
                step="检查 Starsector 目录",
                command=command,
                stdout=[],
                stderr=str(exc),
                return_code=1,
                report_paths=[],
            )
            return
        self.log(f"Starsector 目录有效: {fonts_dir}")
        self.append_full_log(
            step="检查 Starsector 目录",
            command=command,
            stdout=[f"Starsector 目录有效: {fonts_dir}"],
            stderr="",
            return_code=0,
            report_paths=[],
        )
        messagebox.showinfo(APP_TITLE, f"找到字体目录:\n{fonts_dir}")

    def analyze_fontlib_action(self) -> None:
        def work() -> None:
            font_dir = self.require_path(self.source_font_dir, "原字体库目录")
            work_dir = self.require_path(self.work_dir, "输出工作目录")
            config_dir = self.require_path(self.starsector_root, "Starsector 根目录")
            output_dir = work_dir / "fontlib_analysis"
            self.log_thread(f"分析字体库: {font_dir}")
            result = analyze_fontlib(font_dir, config_dir, output_dir)
            self.log_thread(f"已生成字符集: {result.charset_path}")
            self.log_thread(f"已生成报告: {result.report_path}")
            return {
                "command": f"analyze_fontlib --font-dir {font_dir} --config-dir {config_dir} --output {output_dir}",
                "stdout": [
                    f"Scanned {len(result.fonts)} .fnt file(s)",
                    f"Wrote {result.charset_path}",
                    f"Wrote {result.report_path}",
                ],
                "report_paths": [result.charset_path, result.report_path],
            }
        self.run_background("分析当前字体库", work)

    def filter_charset_action(self) -> None:
        def work() -> None:
            font = self.require_path(self.target_font, "目标字体 TTF/OTF")
            work_dir = self.require_path(self.work_dir, "输出工作目录")
            analysis_dir = work_dir / "fontlib_analysis"
            charset = analysis_dir / "charset_union_from_fontlib.txt"
            output = analysis_dir / "charset_supported_by_font.txt"
            self.log_thread(f"过滤字符集: {charset}")
            result = filter_charset_by_font(font, charset, output, force=True)
            self.log_thread(f"输入字符: {result.input_count}")
            self.log_thread(f"支持字符: {result.supported_count}")
            self.log_thread(f"不支持字符: {result.unsupported_count}")
            self.log_thread(f"已生成过滤字符集: {result.output_path}")
            self.log_thread(f"已生成过滤报告: {result.report_path}")
            return {
                "command": f"filter_charset --font {font} --charset {charset} --output {output}",
                "stdout": [
                    f"Input characters: {result.input_count}",
                    f"Supported characters: {result.supported_count}",
                    f"Unsupported characters: {result.unsupported_count}",
                    f"missing_cmap: {result.missing_cmap_count}",
                    f"empty_glyph: {result.empty_glyph_count}",
                    f"Wrote {result.output_path}",
                    f"Wrote {result.report_path}",
                ],
                "report_paths": [result.output_path, result.report_path],
            }
        self.run_background("过滤字符集", work)

    def rebuild_fonts_action(self) -> None:
        def work() -> None:
            config = RebuildConfig(
                font=self.require_path(self.target_font, "目标字体 TTF/OTF"),
                source_font_dir=self.require_path(self.source_font_dir, "原字体库目录"),
                charset=self.require_path(self.work_dir, "输出工作目录") / "fontlib_analysis" / "charset_supported_by_font.txt",
                output_font_dir=self.require_path(self.work_dir, "输出工作目录") / "replacement_fonts",
                atlas_size=int(self.atlas_size.get()),
                force=True,
            )
            self.log_thread(f"生成替换字体: {config.output_font_dir}")
            result = rebuild_fontlib(config)
            for entry in result.entries:
                status = "OK" if entry.success else "FAILED"
                suffix = f" - {entry.error}" if entry.error else ""
                self.log_thread(f"[{status}] {entry.source_fnt.name}{suffix}")
            self.log_thread(f"已生成重建报告: {result.report_path}")
            return {
                "command": (
                    f"rebuild_fontlib --font {config.font} --source-font-dir {config.source_font_dir} "
                    f"--charset {config.charset} --output-font-dir {config.output_font_dir} "
                    f"--atlas-size {config.atlas_size}"
                ),
                "stdout": [
                    f"{'OK' if entry.success else 'FAILED'} {entry.source_fnt.name} {entry.status}"
                    for entry in result.entries
                ] + [f"Wrote {result.report_path}"],
                "report_paths": [result.report_path],
            }
        self.run_background("生成替换字体", work)

    def install_action(self) -> None:
        if not self.confirm_core_overwrite("应用到游戏"):
            return

        def work() -> None:
            work_dir = self.require_path(self.work_dir, "输出工作目录")
            config = InstallConfig(
                starsector_root=self.require_path(self.starsector_root, "Starsector 根目录"),
                replacement_font_dir=work_dir / "replacement_fonts",
                manifest_path=work_dir / "install_manifest.json",
                pack_name=PACK_NAME,
            )
            self.log_thread("正在备份并应用字体...")
            result = install_replacement_fonts(config)
            self.log_thread(f"安装完成，复制文件数: {len(result.installed_files)}")
            self.log_thread(f"备份目录: {result.backup_dir}")
            self.log_thread(f"安装记录: {result.manifest_path}")
            return {
                "command": (
                    f"install_replacement_fonts --starsector-root {config.starsector_root} "
                    f"--replacement-font-dir {config.replacement_font_dir} --manifest {config.manifest_path}"
                ),
                "stdout": [
                    f"Installed files: {len(result.installed_files)}",
                    f"Backup path: {result.backup_dir}",
                    f"Install manifest: {result.manifest_path}",
                ],
                "report_paths": [result.manifest_path],
            }
        self.run_background("应用到游戏", work)

    def restore_action(self) -> None:
        if not self.confirm_core_overwrite("从备份还原"):
            return

        def work() -> None:
            manifest = self.require_path(self.work_dir, "输出工作目录") / "install_manifest.json"
            self.log_thread(f"读取安装记录: {manifest}")
            result = restore_from_manifest(manifest)
            self.log_thread(f"已从备份还原: {result.backup_dir}")
            self.log_thread(f"恢复字体目录: {result.fonts_dir}")
            return {
                "command": f"restore_from_manifest --manifest {manifest}",
                "stdout": [
                    f"Restored fonts directory: {result.fonts_dir}",
                    f"Backup used: {result.backup_dir}",
                ],
                "report_paths": [manifest],
            }
        self.run_background("从备份还原", work)

    def confirm_core_overwrite(self, action: str) -> bool:
        return messagebox.askyesno(
            APP_TITLE,
            f"{action} 是 core-overwrite 操作。\n\n"
            "建议先复制一份 Starsector 测试副本。\n"
            "继续会覆盖 starsector-core\\graphics\\fonts 中的同名字体文件。\n\n"
            "确认继续？",
            icon=messagebox.WARNING,
        )

    def require_path(self, variable: tk.StringVar, label: str) -> Path:
        value = variable.get().strip()
        if not value:
            raise FontGenError(f"请填写: {label}")
        return Path(value)

    def run_background(self, title: str, func) -> None:
        self.log(f"开始: {title}")

        def target() -> None:
            try:
                result = func() or {}
            except Exception as exc:
                error_message = str(exc)
                detail = str(exc)
                if not isinstance(exc, FontGenError):
                    detail = f"{exc}\n{traceback.format_exc()}"
                self.append_full_log(
                    step=title,
                    command=title,
                    stdout=[],
                    stderr=detail,
                    return_code=1,
                    report_paths=[],
                )
                self.log_thread(f"失败: {title}: {detail}")
                self.after(0, lambda message=error_message: messagebox.showerror(APP_TITLE, message))
                return
            self.append_full_log(
                step=title,
                command=str(result.get("command", title)),
                stdout=[str(line) for line in result.get("stdout", [])],
                stderr="",
                return_code=0,
                report_paths=[Path(path) for path in result.get("report_paths", [])],
            )
            self.log_thread(f"完成: {title}")

        threading.Thread(target=target, daemon=True).start()

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def log_thread(self, message: str) -> None:
        self.log_queue.put(message)

    def gui_log_path(self) -> Path:
        work_dir = self.work_dir.get().strip()
        base = Path(work_dir) if work_dir else Path.cwd()
        return base / "starsector_font_replacer_gui.log"

    def append_full_log(
        self,
        *,
        step: str,
        command: str,
        stdout: list[str],
        stderr: str,
        return_code: int,
        report_paths: list[Path],
    ) -> None:
        path = self.gui_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "=" * 80,
            f"time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"step: {step}",
            f"command: {command}",
            "stdout:",
        ]
        lines.extend(f"  {line}" for line in stdout)
        lines.extend(
            [
                "stderr:",
                f"  {stderr}" if stderr else "  <empty>",
                f"return_code: {return_code}",
                "report_paths:",
            ]
        )
        if report_paths:
            lines.extend(f"  {path}" for path in report_paths)
        else:
            lines.append("  <none>")
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        self.log_thread(f"日志文件: {path}")

    def flush_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log(message)
        self.after(100, self.flush_log_queue)


def main() -> int:
    app = FontReplacerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
