# MARS Marketing Simulation - Claude MCP 插件

该项目是基于 OASIS 框架的营销模拟平台，通过 MCP (Model Context Protocol) 与 Claude Desktop 集成，使 Claude 能够设计和执行社交网络营销实验。

## 快速开始

### 步骤 1: 安装 oasis 包

首先创建并激活 conda 环境，然后以可编辑模式安装本地 oasis 包：

```bash
# 创建环境（如果尚未创建）
conda create -n oasis python=3.11 -y
conda activate oasis

# 进入项目目录
cd /path/to/marketing_simulation

# 安装依赖和 oasis 包（可编辑模式）
cd oasis
pip install -e .
cd ..

# 安装 MCP 服务所需的 FastMCP
pip install fastmcp pandas
```

> **注意**：必须使用 `pip install -e .` 安装本地 oasis 包

### 步骤 2: 配置 Claude Desktop MCP 设置

编辑 Claude Desktop 的配置文件，添加 MARS MCP Server：

**macOS 配置文件路径：**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows 配置文件路径：**
```
%APPDATA%\Claude\claude_desktop_config.json
```

添加以下配置（请根据实际路径修改）：

```json
{
  "mcpServers": {
    "mars-marketing": {
      "command": "/opt/anaconda3/envs/oasis/bin/python",
      "args": ["/path/to/marketing_simulation/mcp_server.py"],
      "env": {
        "MARS_MODEL_BASE_URL": "https://api.openai.com/v1",
        "MARS_MODEL_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**配置说明：**
- `command`：oasis 环境中 Python 解释器的完整路径
- `args`：`mcp_server.py` 的完整路径
- `env`：可选，配置模拟所用的 LLM API 端点和密钥

保存配置后，重启 Claude Desktop 即可生效。

### 步骤 3: 让 Claude 学习 Skill 并开始工作

在 Claude Desktop 中，将 `skill.md` 文件内容发送给 Claude，让它学习如何使用 MARS 营销模拟平台：

```
请学习以下 skill 并按照其中的流程执行营销模拟实验：
[粘贴 skill.md 内容]
```

或者直接在对话中附加 `skill.md` 文件。

学习完成后，Claude 将具备以下能力：
1. **环境诊断**：检查运行环境和 API 配置
2. **数据导入**：加载用户画像 CSV
3. **配置模拟**：设置模拟步数和态度指标
4. **设计干预**：创建广播、贿赂、注册机器人等营销干预策略
5. **执行模拟**：运行 OASIS 多智能体模拟
6. **分析结果**：查询数据库，分析态度变化

## 可用 MCP Tools

| 工具名 | 用途 |
|--------|------|
| `get_runtime_defaults` | 查看解析后的路径与环境状态 |
| `save_model_endpoint` | 保存 LLM API 端点和密钥 |
| `cleanup_simulation_environment` | 清理残留进程和数据库锁 |
| `import_user_profiles` | 导入用户画像 CSV |
| `set_simulation_config` | 配置模拟步数和态度指标 |
| `build_intervention_csv` | 构建干预策略 CSV |
| `run_marketing_simulation` | 启动模拟 |
| `read_run_log` | 读取运行日志 |
| `list_db_tables` | 列出数据库表 |
| `query_db_table` | 查询任意表 |
| `get_latest_posts` | 获取最新帖子 |



## 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MARS_SIMULATION_DIR` | 模拟脚本目录 | `simulation/` |
| `MARS_DATA_ROOT` | 数据目录 | `data/` |
| `MARS_PROFILE_PATH` | 用户画像 CSV 路径 | `data/oasis_agent_init.csv` |
| `MARS_DB_PATH` | SQLite 数据库路径 | `data/oasis_database.db` |
| `MARS_MODEL_BASE_URL` | LLM API 基础 URL | - |
| `MARS_MODEL_API_KEY` | LLM API 密钥 | - |

示例对话：
https://claude.ai/share/60ed2805-71cb-4463-bb6c-bf64f343687c