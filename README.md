# Starsector 中文字体替换工具

这个项目是 Starsector 中文字体替换工具 / 外部字体 MOD 工具。当前重点是 Windows 外部工具：分析现有字体库、过滤目标字体支持字符、重建同名覆盖式字体文件，并在用户确认后备份和替换 `starsector-core\graphics\fonts`。

工具不内置任何字体文件，也不内置任何 Starsector 文件。字体、原字体库、Starsector 路径和输出目录都由用户在 GUI 或命令行中选择。

## 素材与版权边界

- 本项目不内置任何 Starsector 文件、游戏字体库、汉化包文件或生成物。
- 本项目不内置任何 `.ttf` / `.otf` 字体文件；用户需要自行提供有合法使用权的字体。
- 用户需要自行提供文本版 AngelCode BMFont 参考文件 `reference/orbitron12.fnt`，工具只读取它来模仿 Starsector 原版 `.fnt` 的 block 结构和字段顺序。
- 本工具仅用于本地字体转换、备份和替换测试；不会自动上传、分发或修改任何真实 Starsector 安装目录。

## 安装

建议在虚拟环境中安装：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

如果需要构建 Windows EXE，安装额外打包依赖：

```powershell
python -m pip install -e .[exe]
```

运行前请把 Starsector 原版参考字体文件放到：

```text
reference/orbitron12.fnt
```

生成器会读取这个文件并尽量保留它的 AngelCode BMFont block 结构和字段顺序。如果该文件不存在，命令会报错。

## Windows GUI

最小 GUI 入口：

```powershell
starsector-fontgen-gui
```

GUI 名称是 **Starsector Font Replacer**，字段包括：

- Starsector 根目录
- 目标字体 TTF/OTF
- 原字体库目录，默认跟随根目录填入 `starsector-core\graphics\fonts`
- 输出工作目录
- atlas size，默认 `4096`

按钮流程：

1. 检查 Starsector 目录
2. 分析当前字体库
3. 过滤字符集
4. 生成替换字体
5. 应用到游戏
6. 从备份还原

“应用到游戏”和“从备份还原”都会先弹窗确认，提醒这是 core-overwrite 操作，建议先复制 Starsector 测试副本，并说明会覆盖 fonts 目录中的同名文件。

注意：“原字体库目录”默认是整个 `starsector-core\graphics\fonts`。如果你只想替换某个汉化包里的字体文件，请改选汉化字体库子集目录；如果选择整个 core fonts 目录，程序会尝试重建里面的所有 `.fnt`。

## 使用

```powershell
starsector-fontgen `
  --font ttf\SourceHanSansCN-Regular.otf `
  --text-dir path\to\starsector-or-mod-data `
  --extra-charset path\to\charset_extra.txt `
  --size 16 `
  --atlas-size 2048 `
  --output output\fonts\myfont16
```

`--extra-charset` 是可选参数。`--atlas-size` 只允许 `512`、`1024`、`2048`、`4096`，默认是 `2048`。MVP 只支持单页图集；如果字符放不下，请增大 `--atlas-size`、减少字符集或降低字号。

你可以把待转换字体集中放在项目根目录的 `ttf/` 文件夹中，然后把 `--font` 指向其中的 `.ttf` 或 `.otf` 文件。

批量生成多个字号时使用 `--sizes`：

```powershell
starsector-fontgen `
  --font ttf\SourceHanSansCN-Regular.otf `
  --text-dir path\to\starsector-or-mod-data `
  --sizes 12,16,20,24 `
  --atlas-size 2048 `
  --output output\fonts\myfont16
```

如果 `--output` 是 `output\fonts\myfont16`，批量模式会把末尾数字替换为每个字号，生成 `myfont12`、`myfont16`、`myfont20`、`myfont24` 这一组文件。传入 `--sizes` 时会忽略单字号的 `--size`。

默认不会覆盖已有文件。需要覆盖时显式传入：

```powershell
starsector-fontgen ... --force
```

## 输出文件

如果 `--output output\fonts\myfont16`，会生成：

```text
output/fonts/myfont16.fnt
output/fonts/myfont16_0.png
output/fonts/myfont16_preview.png
output/fonts/myfont16_report.txt
```

批量模式还会在输出目录生成：

```text
output/fonts/batch_summary_report.txt
output/fonts/patch_instructions.txt
```

`batch_summary_report.txt` 会记录每个字号的生成状态、glyph count、atlas size、atlas 占用率、输出文件路径，以及是否有 unsupported chars。

`patch_instructions.txt` 只提供手动接入说明，不会自动修改 `settings.json`。

如果字体不支持某些字符，或渲染阶段发现非空格字符没有可见 glyph，还会生成：

```text
output/fonts/myfont16_unsupported_chars_report.txt
```

`myfont16_report.txt` 会记录扫描文件数量、编码 fallback 情况、reference `.fnt` 的实际读取编码、字符来源统计、被忽略的控制字符，以及输出摘要。文本读取顺序是 `utf-8-sig`、`utf-8`、`gb18030`；仍失败时会用忽略错误的方式读取，并把该文件标记为 `damaged_encoding`。reference `.fnt` 会按 `utf-8-sig`、`utf-8`、`gb18030`、`cp1252`、`latin-1` 顺序尝试读取。

## 放入 Starsector mod

把生成的 `.fnt` 和 `_0.png` 放进你的 mod 目录，例如：

```text
YourMod/graphics/fonts/myfont16.fnt
YourMod/graphics/fonts/myfont16_0.png
```

这只是第一步。你还必须在 `settings.json` 或对应字体配置中指向新的 `.fnt` 文件，例如 `graphics/fonts/myfont16.fnt`。不要默认直接覆盖 Starsector core 文件；建议始终通过 mod 配置引用生成的字体。

## 分析现有字体库

如果你已经有一套汉化字体库，但不确定哪些 `.fnt` 被配置引用、哪些 PNG 缺失、总字符集包含哪些字符，可以运行只读分析命令：

```powershell
starsector-fontgen-analyze-fontlib `
  --font-dir path\to\graphics\fonts `
  --config-dir path\to\starsector-or-mod-config `
  --output output\fontlib_analysis
```

该命令不会删除任何文件，不会修改 Starsector core，也不会自动修改 `settings.json`。

输出文件：

```text
output/fontlib_analysis/charset_union_from_fontlib.txt
output/fontlib_analysis/fontlib_analysis_report.md
```

`fontlib_analysis_report.md` 会列出每个 `.fnt` 的 face、size、lineHeight、atlas 尺寸、page file、PNG 是否存在、chars count、是否被 `settings.json` 或其他文本配置引用、独有字符数量、可能重复的字体文件，以及保留建议。保留建议是人工判断辅助，不会自动删除疑似备用文件。

## 过滤字符集到目标字体支持范围

如果目标字体不覆盖完整汉化字符集，生成时可能出现 `reason=missing_cmap`。这时可以先把分析得到的总字符集过滤到目标字体支持的范围：

```powershell
starsector-fontgen-filter-charset `
  --font ttf\Uranus_Pixel_11Px.ttf `
  --charset output\fontlib_analysis\charset_union_from_fontlib.txt `
  --output output\fontlib_analysis\charset_supported_by_font.txt
```

该命令会生成：

```text
output/fontlib_analysis/charset_supported_by_font.txt
output/fontlib_analysis/charset_filter_report.txt
```

`charset_filter_report.txt` 会列出输入字符总数、支持字符数、不支持字符数，以及不支持字符的字符本身、Unicode code point 和 Unicode name。普通空格 U+0020 会被保留。

过滤后的字符集可以作为 `--extra-charset` 再生成字体：

```powershell
starsector-fontgen `
  --font ttf\Uranus_Pixel_11Px.ttf `
  --text-dir test_texts `
  --extra-charset output\fontlib_analysis\charset_supported_by_font.txt `
  --sizes 12,16,20,24 `
  --output output\fonts\myfont16
```

注意：过滤字符集有缺字风险。它能让当前字体成功生成，但被过滤掉的字符如果在游戏文本中出现，仍然会缺字。使用前请人工检查 `charset_filter_report.txt`。

## 覆盖式汉化包测试流程

有些旧汉化包通过覆盖 Starsector core 源文件工作，而不是外挂式 mod。生成器可以按现有字体库的 `.fnt` 文件名和 page PNG 文件名重建一套 replacement 字体包，但不会自动覆盖原文件，也不会修改 Starsector core。

```powershell
starsector-fontgen-rebuild-fontlib `
  --font ttf\Uranus_Pixel_11Px.ttf `
  --source-font-dir path\to\existing_cn_fontlib\graphics\fonts `
  --charset output\fontlib_analysis\charset_supported_by_font.txt `
  --output-font-dir output\replacement_fonts `
  --atlas-size 4096 `
  --force
```

输出示例：

```text
output/replacement_fonts/orbitron24aabold.fnt
output/replacement_fonts/orbitron24aabold_0.png
output/replacement_fonts/rebuild_fontlib_report.md
```

生成的 `.fnt` 会保留源 `.fnt` 的文件名，并保留源 `.fnt` 中的 page file 名称，例如 `orbitron24aabold_0.png`。

安全测试流程：

1. 先完整复制一份 Starsector 测试副本。
2. 只在测试副本中替换字体文件。
3. 禁止直接覆盖你的唯一 Starsector 游戏目录。
4. 替换前保留原始 `graphics/fonts` 备份。
5. 查看 `rebuild_fontlib_report.md`，确认每个 `.fnt` 都成功、glyph count 合理、无 unsupported chars，再进入游戏测试。

## 生成覆盖式字体发布包

重建出 replacement 字体目录后，可以封装成一个可分发的覆盖式字体替换包。这个步骤只创建 release 包目录，不会自动操作真实 Starsector 目录。

```powershell
starsector-fontgen-build-pack `
  --replacement-font-dir output_stage4\replacement_fonts `
  --report output_stage4\replacement_fonts\rebuild_fontlib_report.md `
  --output-pack output_release\Starsector-Uranus-Font-Pack `
  --pack-name "Starsector Uranus Pixel Font Pack" `
  --force
```

输出包结构：

```text
output_release/Starsector-Uranus-Font-Pack/
  replacement_fonts/
  rebuild_fontlib_report.md
  manifest.json
  install_font_pack.ps1
  uninstall_font_pack.ps1
  README.md
```

`manifest.json` 会记录包名、构建时间、replacement 字体文件列表、源报告路径、文件数量和 core-overwrite 警告。

安装脚本行为：

- 提示用户输入 Starsector 根目录；
- 检查 `starsector-core\graphics\fonts` 是否存在；
- 在 Starsector 根目录下创建 `backups\fonts_backup_YYYYMMDD_HHMMSS`；
- 备份原 fonts 文件夹；
- 只复制 `replacement_fonts` 中的 `.fnt` 和 `.png` 到游戏 fonts 目录；
- 在包目录生成 `install_manifest.json`；
- 打印安装完成和备份路径。

卸载脚本会读取 `install_manifest.json`，找到备份目录并恢复原 fonts 文件夹。安装和卸载脚本都不要求管理员权限。

## 无 Python 环境使用方法

开发机上可以用 PyInstaller 构建 Windows EXE：

```powershell
.\build_exe.ps1
```

脚本会把以下命令打包到 `dist/`：

```text
dist/starsector-fontgen.exe
dist/starsector-fontgen-analyze-fontlib.exe
dist/starsector-fontgen-filter-charset.exe
dist/starsector-fontgen-rebuild-fontlib.exe
dist/starsector-fontgen-build-pack.exe
dist/starsector-fontgen-gui.exe
```

之后在没有 Python 环境的 Windows 机器上，可以直接运行这些 EXE，例如：

```powershell
.\dist\starsector-fontgen-analyze-fontlib.exe `
  --font-dir path\to\graphics\fonts `
  --config-dir path\to\config `
  --output output\fontlib_analysis
```

EXE 只包含程序代码和 Python 运行时依赖，不会打包 `.venv`、`output`、测试字体库、现有汉化字体库或任何 Starsector 游戏文件。字体文件、reference `.fnt`、字符集文件和输入/输出目录仍然由 GUI/命令行参数指定。

## 字符集规则

最终字符集来自三部分：

- `--text-dir` 扫描到的文本字符
- `--extra-charset` 中的字符
- 内置 preview 文本中的字符

生成器会忽略换行、回车、制表符、BOM、零宽字符等控制字符，但会保留普通空格 U+0020。普通空格即使没有 visible bbox，也会生成 `.fnt` char entry，并设置合理的 `xadvance`。

## 参考文件

项目不会内置伪造的 Starsector 原版 `.fnt`。请自行从你的 Starsector 安装或可用资源中放入。
