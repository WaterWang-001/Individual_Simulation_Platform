# 路径硬编码审计

## 结论

- 原始 `自动化问答` 工程不是“全部相对路径软编码”。
- 当前 `fastmcp_claude_plugin/` 已整理为自洽目录，默认使用本目录内的 `core/`、`prompts/`、`benchmarks/`、`benchmark_sources/`、`outputs/`。

### 相对健康的部分

这些脚本主要依赖 `BASE_DIR` / `Path(__file__)` / `os.path.dirname(os.path.abspath(__file__))` 拼接相对路径，属于可迁移写法：

- `run_benchmark.py`
- `run_all_benchmarks.py`
- `build_benchmark.py`
- `prepare_benchmark_sources.py`
- `fastmcp_claude_plugin/*`（已进一步调整为读写本目录，并对外返回相对路径）

### 明确存在绝对路径/环境绑定的部分

1. 旧脚本中的硬编码绝对路径
   - `build_benchmark.py`
   - `agentic_benchmark.py`

2. 已生成数据中的绝对路径
   - `benchmark_sources/*/meta.json`
   - `benchmarks/*/mapping.json`
   - `outputs_02/*.jsonl`
   - `outputs/preset_replay_shortlist.json`
   - 部分 `demo_web_streamlit/examples/preset/*/mapping.json`

3. 插件运行时内部仍会解析成绝对路径
   - 这是 Python 运行时定位工程目录的正常行为
   - 但插件对外返回现在已默认转成相对路径

## 当前处理策略

- 已把 FastMCP 所需代码、数据、运行脚本复制到本目录
- 已清洗本目录下：
  - `benchmark_sources/*/meta.json`
  - `benchmarks/*/mapping.json`
  - `outputs/*.jsonl`
- `scripts/clean_historical_paths.py` 现在针对本目录运行

## 建议

如果下一步目标是“整个仓库可迁移到 GitHub 后无本机路径泄露”，还需要继续清洗原始主工程和 demo 目录中的历史数据：

1. 清洗 `benchmark_sources/*/meta.json`
2. 清洗 `benchmarks/*/mapping.json`
3. 清洗 `outputs_*/*.jsonl`
4. 清洗 `demo_web_streamlit/examples/preset/*/mapping.json`
