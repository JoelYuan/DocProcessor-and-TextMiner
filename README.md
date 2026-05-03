# 文档处理工具集

这是一个用于处理和转换各种文档格式的 Python 工具集。

## 目录

- [环境准备](#环境准备)
- [程序介绍](#程序介绍)
- [运行指令](#运行指令)

---

## 环境准备

### 1. 激活 Conda 环境

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate rtx5060
```

### 2. 安装依赖库

程序会自动检测并安装缺少的依赖，也可以手动安装：

```bash
pip install xlrd openpyxl python-docx python-pptx
```

依赖说明：
- `xlrd` - 读取 .xls 文件
- `openpyxl` - 读取 .xlsx 文件
- `python-docx` - 读取 .docx 文件
- `python-pptx` - 读取 .pptx 文件

---

## 程序介绍

### 1. xls转md.py

**功能：** 单个 Excel 文件转换为 Markdown

- 支持格式：.xls, .xlsx
- 弹窗选择文件，弹窗保存位置
- 支持多 Sheet 表格

### 2. 文件夹文档汇总.py

**功能：** 汇总整个文件夹内容为一个 Markdown 文件

- 自动生成项目目录树
- 支持文件格式：
  - Excel：.xls, .xlsx
  - Word：.docx
  - PowerPoint：.pptx
  - 文本/代码：.txt, .md, .py, .js, .json, .xml, .html, 等等
- 输出为与文件夹同名的 .md 文件

### 3. 项目分析.py

**功能：** 项目架构分析与增量学习

- 生成项目架构文件
- 使用 LM Studio 进行实体关系提取
- 记忆化学习，支持断点续传

### 4. 读书助手.py

**功能：** 文档知识图谱构建工具

- 分块处理长文档
- 与 LM Studio 交互提取知识图谱
- 支持文档类型：
  - `textbook` - 教材/技术文档
  - `novel` - 小说/文学
  - `paper` - 学术论文
- 支持文件格式：.txt, .md, .pdf, .json, .xml, .html

---

## 运行指令

### 运行 xls转md.py

```bash
cd /home/yuan/文档/Python_Project/txt-read-all
conda activate rtx5060
python xls转md.py
```

### 运行 文件夹文档汇总.py

```bash
cd /home/yuan/文档/Python_Project/txt-read-all
conda activate rtx5060
python 文件夹文档汇总.py
```

### 运行 项目分析.py

```bash
cd /home/yuan/文档/Python_Project/txt-read-all
conda activate rtx5060
python 项目分析.py
```

### 运行 读书助手.py

**用法：**
```bash
cd /home/yuan/文档/Python_Project/txt-read-all
conda activate rtx5060
python 读书助手.py <textbook|novel|paper> [文件路径]
```

**示例：**
```bash
# 分析教材（弹窗选择文件）
python 读书助手.py textbook

# 分析小说（指定文件）
python 读书助手.py novel story.md

# 分析论文
python 读书助手.py paper research.pdf
```

---

## 注意事项

- **旧版 Office 格式（.doc/.ppt）**：目前不支持，建议先转换为 .docx/.pptx
- **文件大小限制**：单个文件超过 10MB 会被跳过
- **LM Studio**：项目分析和读书助手需要 LM Studio 运行
