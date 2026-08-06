# Godette Codex 宠物与 PetDiff CI

这是一个完整可运行的 Codex v2 动画宠物项目。人物采用已经存在的
[Godette / Godot-chan](https://github.com/godotengine/godot-design/tree/7d12f300c377712028e9af6be01511b3e05a534c/godette)，
不是虚构的新角色。仓库同时提供 `PetDiff CI`：面向所有 Codex v2
宠物的确定性视觉回归引擎。

项目不是界面空壳。Python 包会验证真实图集、渲染确定性 GIF/WebP、
对 74 个必用单元格逐格比较、输出 JSON/HTML/PNG 差异证据、完成安全
安装和回滚，并构建字节可复现的发布包。

[English](README.md) | [在线 PetDiff Lab](https://kanadek.github.io/godette-codex-pet/)

![Godette 在 Codex 中呼吸与眨眼的待机动画](docs/media/godette-idle.gif)

## 为什么选择 Godette

Godette 是 Godot 官方设计仓库中的既有人物，具有明确的 CC BY 4.0
授权和可核验的人物设定。她和高知名度的 Godot Engine 直接相关，同时
在检索时没有发现 Godette Codex 宠物仓库。

开发期间只读复核发现，新的并行项目已经开始实现“JSONL 会话转动画”，
因此本项目没有继续把它包装成卖点，而是把核心转为没有发现同类实现的
`PetDiff CI`。研究过程与候选淘汰依据见
[docs/RESEARCH.md](docs/RESEARCH.md)。

## 可运行能力

- 完整 Codex v2 包：1536 x 2288、8 x 11、74 个必用格、14 个透明空格。
- 校验 manifest、尺寸、透明像素、隐藏 RGB、色键残留、边缘裁切和体积。
- 比较 baseline 与 candidate 的全部必用格，输出逐格像素变化率。
- 检测轮廓中心位移，并按显式预算决定 CI 通过或失败。
- 生成机器可读 JSON、离线 HTML 和高亮差异图。
- 提供可复用的 GitHub Composite Action。
- 提供严格 JSONL 动画夹具和确定性 GIF/WebP 渲染。
- 安装前校验、锁、备份、回滚、可恢复卸载和 doctor 修复建议。
- 跨平台拒绝 ZIP 路径逃逸、同名覆盖、符号链接和解压膨胀。
- 固定 ZIP 元数据和逐文件 SHA-256，保证发布包可复现。

## 安装与验收

```bash
git clone https://github.com/KanadeK/godette-codex-pet.git
cd godette-codex-pet
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

godette-pet validate pet --strict --json
godette-pet install --source pet --dry-run --json
godette-pet install --source pet --json
godette-pet doctor --source pet --json
```

Windows 创建虚拟环境后跳过 `source`，并把 `python` 替换为
`.\.venv\Scripts\python.exe`。

## 运行 PetDiff

```bash
godette-pet diff baselines/godette pet \
  --output-dir dist/petdiff \
  --max-changed-cells 0 \
  --max-cell-change-ratio 0 \
  --max-bbox-shift-px 0 \
  --json
```

- 退出码 `0`：候选图集满足预算。
- 退出码 `1`：候选图集超过预算，查看 `dist/petdiff/report.html`。
- 退出码 `2`：输入包或预算本身无效。

有意调整一个格时，必须显式声明预算，例如：

```bash
godette-pet diff baselines/godette pet \
  --output-dir dist/petdiff \
  --max-changed-cells 1 \
  --max-cell-change-ratio 0.03 \
  --max-bbox-shift-px 2
```

PetDiff 不会默许变更。CI 策略和报告字段见
[docs/PETDIFF.md](docs/PETDIFF.md)。

## 发布前门禁

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest --cov=godette_pet --cov-report=term-missing
node --test web/tests/*.test.mjs
python -m build
python scripts/release_check.py --json
```

最后一条命令会检查真实宠物包、两组示例、回放确定性、自身视觉回归、
发布 ZIP 可复现性、文档完整性和 Pages 构建。任一失败都禁止发布。

## 安全卸载与修复

```bash
godette-pet uninstall --dry-run --json
godette-pet uninstall --json
godette-pet rollback --json
godette-pet doctor --source pet --json
```

卸载只是把当前宠物移入 `pet-backups`，不会删除。常见失败对应的准确
修复步骤、保留证据和禁止操作见 [docs/REPAIR.md](docs/REPAIR.md)。

## 授权

代码使用 MIT License。Godette 参考图和本项目生成的衍生宠物美术使用
CC BY 4.0。人物设计署名 Andrea Calabró；参考图固定到
`godotengine/godot-design` 的 commit
`7d12f300c377712028e9af6be01511b3e05a534c`。

重新分发美术前请阅读 [ASSET_LICENSE.md](ASSET_LICENSE.md) 和
[NOTICE.md](NOTICE.md)。本项目为非官方项目，与 Godot Engine、
Godot Foundation、OpenAI 和 Codex 无隶属或背书关系。
