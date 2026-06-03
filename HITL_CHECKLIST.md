# HITL Checklist

| Check Item | What To Inspect | Pass Criteria | Result |
|---|---|---|---|
| 命令是否成功 | 运行 `starsector-fontgen` 的终端输出 | 单字号模式输出 4 个主文件和 patch instructions；批量模式输出每个字号状态、`batch_summary_report.txt`、`patch_instructions.txt` | 通过 |
| 是否生成 `.fnt` | 输出目录中的 `myfontXX.fnt` | 每个目标字号都有对应 `.fnt` 文件 | 通过 |
| 是否生成 `_0.png` | 输出目录中的 `myfontXX_0.png` | 每个目标字号都有对应单页 atlas PNG | 通过 |
| 是否生成 `preview.png` | 输出目录中的 `myfontXX_preview.png` | 每个目标字号都有 preview PNG | 通过 |
| preview 中文是否可读 | 打开 `myfontXX_preview.png` | 中文、英文、数字和标点可读，无明显重叠 | 已目视通过 |
| atlas 是否为空 | 打开 `myfontXX_0.png` 或检查图片 alpha | 图集中能看到白色 glyph，透明背景正常 | 通过 |
| report 是否有 damaged encoding | 查看 `myfontXX_report.txt` | `Damaged Encoding Files` 为 `<none>`，或已确认损坏文件可接受 | 通过 |
| 是否有 unsupported chars | 查看终端输出和 `*_unsupported_chars_report.txt` | 无 unsupported/empty glyph 报告；若有，先换字体或减少字符集 | 通过 |
| 是否适合进入 Starsector/mod 测试 | 综合 `.fnt`、atlas、preview、report | 文件齐全、preview 可读、无缺字报告、atlas 非空 | 合适 |
