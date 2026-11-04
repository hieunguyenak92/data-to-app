# Data to App

### 让文件成为软件，让你的决定延续到下一次导入。

[English](README.md) · [Tiếng Việt](README.vi.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [简体中文](README.zh-CN.md) · [ไทย](README.th.md) · [Français](README.fr.md)

**把文件和真实任务交给 Claude 或 Codex，获得一个可以运行、检查并由你掌握的应用。**

Data to App 将 CSV 和 Excel 变成可追踪数据来源的业务软件：记录搜索、实用视图、允许的编辑与重复导入。Agent 塑造工作流程，行为确定的 Python/SQLite 引擎分别管理源记录、本地修改和新快照。你获得可运行的应用、源代码与本地数据。

**[创建第一个工作区](#运行库存工作区)** · **[安装到 Claude 或 Codex](docs/INSTALL.md)** · **[探索数据契约](docs/DATA-CONTRACT.md)** · **[探索引导演示](https://hieunguyenak92.github.io/data-to-app/)**

![Data to App 生成的合成库存工作区](docs/assets/workspace.jpg)

*使用合成数据的真实本地运行界面。新快照已完成对账，并保留了本地修改决定。*

> **让下一次导入清清楚楚。** 源值是 `12`，你改成 `20`，新文件却写着 `14`。Data to App 保留你的 `20`，并展示源值、本地值与新值的冲突，由你决定。一致的修改会收敛，不同的决定会保持可见。

## 从实际任务开始

[安装 skill](docs/INSTALL.md) 后，向 agent 提出请求：

> 使用 Data to App 处理 `./exports`。建立本地库存工具，支持库存搜索、低于补货阈值的视图，以及编辑补货阈值和备注。导入下一份文件时保留这些修改，并显示需要我决定的变化。启动应用并验证主要操作。

Skill 引导 agent 检查文件、选择记录标识与操作、构建应用并实际使用它。你描述工作，agent 处理技术模型。如果键、单位或业务规则存在影响结果的歧义，它可能需要你给出一个明确答案。

适合的起点包括库存与订单导出、需要持续修正的联系人列表，以及通过定期文件更新的项目或服务记录。首个版本聚焦于具有独立键的本地表和所请求的工作流程。

## 为下一次导入而设计

| 能力 | 带来的价值 |
| --- | --- |
| **考虑记录身份的分析** | 提供候选键、缺失值、重复记录和前导零标识符的证据。 |
| **连接预检** | 在合并数据前检查未匹配的键和行数膨胀风险。 |
| **三方对账** | 分离源值、本地值和新值，按字段处理编辑冲突。 |
| **导入预览** | 应用快照前查看新增、更新、缺失记录与冲突。 |
| **业务操作界面** | 搜索、配置视图、允许的编辑、冲突解决、历史与 CSV 导出。 |
| **可移植应用源码** | 生成 Python/SQLite 应用和本地资源，独立于已安装 skill 运行。 |

这些机制为 agent 提供判断依据。一列在当前文件中唯一，只能说明它是候选键，不能证明它是稳定的业务身份。连接成功也不能证明合计具有你需要的业务含义。

## 运行库存工作区

需要 **Python 3.10+**。CSV 读取和生成的运行时使用标准库。附带的数据均为合成数据。

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

打开 **http://127.0.0.1:8765**。搜索产品、打开编辑器、修改允许的字段并导出结果。工作区将状态保存在自己的 SQLite 数据库中，重启应用后仍然保留。

在仓库目录的另一个终端预览下一份产品快照：

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

加上 `--apply` 可应用导入，也可使用应用中的预览和确认。尝试编辑一个在新文件中也发生变化的字段，即可体验冲突处理。

导入代表**一张表的完整快照**。快照中没有的记录会标记为缺失并保留。因此，只有部分记录的导出文件会让其余记录被标记为缺失。模式变化以及同键不同值的重复记录会在写入前被拒绝。

## 使用自己的文件

CSV 是文本表格；XLSX 是 Excel 工作簿。处理 XLSX 时，请在运行工具的 Python 环境中安装可选读取器：

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

输入上限为**每文件 10 MiB、每表 50,000 行、200 列、1,000,000 个单元格**。XLSX 默认读取第一个工作表，有其他工作表时会提示。不会重新计算公式。

可以使用上面的提示词，也可以直接检查文件：

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
```

Agent 可根据分析结果配置模型并建立工作区。技术步骤详见[英文安装与 CLI 文档](docs/INSTALL.md)。

## 导出、所有权与边界

CSV 导出包含有效记录的当前值，包括已接受的本地编辑。为降低电子表格公式风险，某些导出单元格前可能加上单引号；内部存储值不变。缺失记录继续保留在本地。

生成的服务绑定到 `127.0.0.1`，使用本地资源，核心操作无需托管服务。Agent 构建应用时，AI 宿主的文件访问和数据政策仍然适用。数据库、输入及导出可能包含敏感信息。参阅[英文隐私文档](docs/PRIVACY.md)。

本版本是本地工作区，不提供多用户认证或云部署保证。它不会执行电子表格公式，也不承诺推断所有业务规则、任意模式迁移或通用数据恢复。将重要结果用于实际业务前，请先检查。

**先体验合成数据工作区，再把真实任务交给 agent。**
