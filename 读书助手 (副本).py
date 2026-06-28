import os
import time
import sys
import json
import requests
import re

# ================= 通用配置区 =================
default_config = {
    "lm_studio_url": "http://localhost:1234/v1/chat/completions",
    "model_name": "default-model",
    "inner_chunk_lines": 400,
    "temperature": 0.15,
    "max_tokens": 1800,
    "request_timeout": 200,
    "retry_times": 3,
    "request_sleep_sec": 1.2
}

# ================= 极简提示词模板 =================
DIR_TREE_PROMPT = """
下面是一个完整项目的树形目录结构。请作为高级软件架构师，梳理并输出该项目的整体架构总结：
1. 划分核心模块并说明职责；
2. 梳理整体技术栈与业务定位；
3. 要求：简洁分段，纯自然语言描述，禁止输出JSON或Markdown列表代码块。

项目目录树：
{tree_content}

直接输出项目整体架构总结：
"""

FILE_READ_PROMPT = """
请阅读以下源码片段，并为其编写一份极简的“全系统备注”：

文件路径：【{file_path}】
代码内容：
{chunk}

输出要求（严格遵守，不要有任何多余的寒暄或前言）：
1. 关键功能描述：用1-3句话通俗说明该文件的核心职责、数据流向及与其他模块的关联。
2. 核心函数/类定义：仅列出关键的函数名/类名，并用简短的一句话说明其作用。

输出格式示例：
【关键功能描述】
...
【核心函数/类定义】
- 函数名/类名：作用说明
- 函数名/类名：作用说明
"""

# ================= 核心工具函数 =================
def split_tree_and_files(file_path):
    """
    适配新的Markdown汇总格式：
    1. 提取 ``` 包裹的目录树
    2. 按 '## 文件: xxx' 切分源码文件
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='gbk') as f:
            content = f.read()

    # 1. 提取目录树（匹配第一个 ``` 到第二个 ``` 之间的内容）
    tree_match = re.search(r'```(.*?)```', content, re.DOTALL)
    tree_text = tree_match.group(1).strip() if tree_match else ""

    # 2. 按 '## 文件: xxx' 切分源码
    file_segments = []
    # 使用正则查找所有文件标题及其位置
    file_headers = list(re.finditer(r'^## 文件:\s*(.+)$', content, re.MULTILINE))
    
    for i, match in enumerate(file_headers):
        file_name = match.group(1).strip()
        start_pos = match.end()
        end_pos = file_headers[i+1].start() if i+1 < len(file_headers) else len(content)
        
        # 提取该文件下的代码块内容
        file_content = content[start_pos:end_pos]
        code_match = re.search(r'```.*?\n(.*?)```', file_content, re.DOTALL)
        code_text = code_match.group(1) if code_match else ""
        
        if code_text.strip():
            lines = code_text.split('\n')
            file_segments.append((file_name, lines))

    return tree_text, file_segments

def iterate_file_inner_chunks(file_path, lines, chunk_lines):
    """单个文件内部按行数切小块"""
    block_id = 0
    for i in range(0, len(lines), chunk_lines):
        slice_lines = lines[i:i + chunk_lines]
        yield block_id, file_path, "\n".join(slice_lines)
        block_id += 1

def call_local_llm(prompt):
    """带重试、空输出拦截的模型调用"""
    payload = {
        "model": default_config["model_name"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": default_config["temperature"],
        "max_tokens": default_config["max_tokens"]
    }
    retry_count = 0
    while retry_count <= default_config["retry_times"]:
        try:
            resp = requests.post(
                default_config["lm_studio_url"],
                json=payload,
                timeout=default_config["request_timeout"]
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if not content:
                raise Exception("模型输出空白字符串")
            return content
        except Exception as e:
            retry_count += 1
            print(f"  [重试 {retry_count}/{default_config['retry_times']}] 异常：{str(e)}")
            time.sleep(2)
    print("  [警告] 多次调用失败，跳过当前片段")
    return None

# ================= 极简版报告生成 =================
def init_log_file(log_path, tree_summary):
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("# 项目阅读完整记录\n\n")
        f.write("## 一、项目整体目录架构总览\n")
        f.write(tree_summary + "\n\n")
        f.write("=" * 80 + "\n\n")

def append_file_log(log_path, block_idx, file_path, summary):
    """极简版日志追加：只写路径和总结"""
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"### 📄 文件：{file_path} ｜ 片段 {block_idx}\n")
        f.write(summary + "\n\n")
        f.write("-" * 60 + "\n\n")

def export_final_report(log_path, md_out):
    if not os.path.exists(log_path):
        print("无阅读日志，无法生成报告")
        return
    with open(log_path, "r", encoding="utf-8") as log_f:
        full_text = log_f.read()
    with open(md_out, "w", encoding="utf-8") as md_f:
        md_f.write("# 项目完整阅读报告\n\n")
        md_f.write(full_text)
    print(f"\n✅ 完整阅读报告已导出：{md_out}")

# ================= 主执行流程 =================
def run_full_read_flow(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    log_file = f"{base_name}_阅读日志.txt"
    report_md = f"{base_name}_阅读报告.md"
    progress_file = f"{base_name}_progress.json"

    print(f"🚀 开始解析文件：{file_path}")
    tree_text, file_list = split_tree_and_files(file_path)

    # 1. 全局架构分析
    if tree_text.strip():
        print("📊 步骤1：提取项目树形目录，生成全局架构认知...")
        dir_prompt = DIR_TREE_PROMPT.format(tree_content=tree_text)
        tree_summary = call_local_llm(dir_prompt) or "目录树解析失败，无全局架构总结"
        init_log_file(log_file, tree_summary)
        print("✅ 项目整体目录架构分析完成\n")
    else:
        init_log_file(log_file, "文件未检测到项目树形目录")

    # 2. 加载进度（断点续传）
    processed_blocks = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as pf:
            processed_blocks = set(json.load(pf))
        print(f"🔄 检测到历史进度，已跳过 {len(processed_blocks)} 个已处理片段")

    # 3. 逐文件阅读
    total_blocks = sum((len(lines) // default_config["inner_chunk_lines"]) + 1 for _, lines in file_list)
    current_block = 0

    for f_path, f_lines in file_list:
        for block_idx, fname, chunk_txt in iterate_file_inner_chunks(f_path, f_lines, default_config["inner_chunk_lines"]):
            current_block += 1
            block_key = f"{fname}_{block_idx}"
            
            if block_key in processed_blocks:
                continue

            print(f"  [{current_block}/{total_blocks}] 处理 {fname} 片段 {block_idx}")
            prompt = FILE_READ_PROMPT.format(file_path=fname, chunk=chunk_txt)
            res = call_local_llm(prompt)
            
            if res:
                append_file_log(log_file, block_idx, fname, res)
                processed_blocks.add(block_key)
                with open(progress_file, 'w') as pf:
                    json.dump(list(processed_blocks), pf)
            
            time.sleep(default_config["request_sleep_sec"])

    # 4. 导出报告
    export_final_report(log_file, report_md)

# ================= 程序入口 =================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python universal_reader.py <你的项目汇总.md>")
        sys.exit(1)
    target_txt = sys.argv[1]
    if not os.path.exists(target_txt):
        print(f"❌ 错误：文件不存在 {target_txt}")
        sys.exit(1)
    run_full_read_flow(target_txt)