import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import filedialog, messagebox


# --- 配置加载 ---
def load_config(config_file: str = "config.json") -> Dict[str, Any]:
    """从配置文件加载模型配置"""
    default_config = {
        "lm_studio_url": "http://localhost:1234/v1/chat/completions",
        "model_name": "gemma-4-26b-a4b-it-uncensored",
        "chunk_size": 10,
        "max_context_items": 5,
        "temperature": 0.1,
        "max_tokens": 2048
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except:
            print(f"Warning: Failed to load {config_file}, using defaults")
    
    return default_config


DEFAULT_CONFIG = load_config()


# --- Notebook 记忆库 ---
class Notebook:
    """持久化记忆库 - 存储实体、关系和层级映射"""
    
    def __init__(self, notebook_file: str):
        self.notebook_file = notebook_file
        self.memory = self._load_notebook()
    
    def _load_notebook(self) -> Dict[str, Any]:
        """加载已识别的结果，实现'不遗忘'的基础"""
        if os.path.exists(self.notebook_file):
            try:
                with open(self.notebook_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                print(f"Warning: Failed to load {self.notebook_file}, starting fresh")
        return {
            "entities": [],
            "relations": [],
            "parent_map": {},
            "parsed_lines": [],
            "summary": ""
        }
    
    def _save_notebook(self):
        """持久化已识别的结果"""
        # 不保存 parsed_lines 到 JSON 文件
        data_to_save = {k: v for k, v in self.memory.items() if k != "parsed_lines"}
        with open(self.notebook_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    
    def add_entity(self, entity: Dict[str, Any]) -> bool:
        """添加实体，去重逻辑"""
        entity_key = self._get_entity_key(entity)
        existing_keys = [self._get_entity_key(e) for e in self.memory["entities"]]
        if entity_key not in existing_keys:
            self.memory["entities"].append(entity)
            self._save_notebook()
            return True
        return False
    
    def add_relation(self, relation: Dict[str, Any]) -> bool:
        """添加关系，去重逻辑"""
        relation_key = self._get_relation_key(relation)
        existing_keys = [self._get_relation_key(r) for r in self.memory["relations"]]
        if relation_key not in existing_keys:
            self.memory["relations"].append(relation)
            self._save_notebook()
            return True
        return False
    
    def add_parent_mapping(self, node_id: str, parent_id: str):
        """添加层级映射"""
        if node_id not in self.memory["parent_map"]:
            self.memory["parent_map"][node_id] = parent_id
            self._save_notebook()
    
    def update_parsed_lines(self, line_numbers: List[int]):
        """记录已解析的行号"""
        for num in line_numbers:
            if num not in self.memory["parsed_lines"]:
                self.memory["parsed_lines"].append(num)
        self.memory["parsed_lines"] = sorted(list(set(self.memory["parsed_lines"])))
        self._save_notebook()
    
    def update_summary(self):
        """更新知识摘要"""
        entity_names = [e.get("name", "") for e in self.memory["entities"]]
        relation_count = len(self.memory["relations"])
        self.memory["summary"] = (
            f"已识别 {len(self.memory['entities'])} 个实体: {', '.join(entity_names[:10])}..."
            f"\n已识别 {relation_count} 个关系"
        )
        self._save_notebook()
    
    def _get_entity_key(self, entity: Dict[str, Any]) -> str:
        """生成实体唯一标识"""
        name = entity.get("name", "").lower()
        node_id = entity.get("node_id", "").lower()
        return f"{name}|{node_id}"
    
    def _get_relation_key(self, relation: Dict[str, Any]) -> str:
        """生成关系唯一标识"""
        source = relation.get("source", "").lower()
        target = relation.get("target", "").lower()
        rel_type = relation.get("type", "").lower()
        return f"{source}|{target}|{rel_type}"
    
    def retrieve_relevant_context(self, current_chunk: str, max_items: int = 5) -> str:
        """根据当前chunk检索相关上下文"""
        relevant_entities = []
        chunk_lower = current_chunk.lower()
        
        for entity in self.memory["entities"]:
            entity_name = entity.get("name", "").lower()
            if entity_name in chunk_lower:
                relevant_entities.append(entity)
        
        for relation in self.memory["relations"]:
            source = relation.get("source", "").lower()
            target = relation.get("target", "").lower()
            if source in chunk_lower or target in chunk_lower:
                relevant_entities.append({"relation": relation})
        
        context_items = relevant_entities[:max_items]
        return json.dumps(context_items, ensure_ascii=False) if context_items else "{}"


# --- TextParser 文本解析器 ---
class TextParser:
    """文本解析器 - 逐行读取并分块处理"""
    
    def __init__(self, source_file: str):
        self.source_file = source_file
    
    def read_lines(self) -> List[str]:
        """读取所有行"""
        with open(self.source_file, 'r', encoding='utf-8') as f:
            return f.readlines()
    
    def chunk_lines(self, lines: List[str], chunk_size: int = 5) -> List[str]:
        """将行分块"""
        chunks = []
        for i in range(0, len(lines), chunk_size):
            chunk = "".join(lines[i:i+chunk_size])
            chunks.append(chunk)
        return chunks


# --- ReasoningEngine 推理引擎 ---
class ReasoningEngine:
    """推理引擎 - 调用LM Studio API进行增量解析"""
    
    def __init__(self, lm_studio_url: str, model_name: str, temperature: float = 0.1, max_tokens: int = 2048):
        self.lm_studio_url = lm_studio_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    def call_lm_studio(self, current_chunk: str, context_from_notebook: str) -> Optional[Dict[str, Any]]:
        """调用模型，并将笔记本作为上下文输入"""
        prompt = (
            f"## Context from previous parsing (已有的知识):\n{context_from_notebook}\n\n"
            f"## New text to parse (新文本):\n{current_chunk}\n\n"
            f"## Task (任务):\n分析这段代码架构，提取：\n"
            f"1. **实体(entities)**: 节点(Node)、服务(Service)、类型(Type)、文件(File)等\n"
            f"2. **关系(relations)**: 层次关系、依赖关系、包含关系\n"
            f"3. **parent_map**: 节点的父子层级映射\n\n"
            f"## Output Format (输出格式):\n"
            f"请输出JSON格式，包含以下字段：\n"
            f"- entities: [{{name: 'xxx', type: 'Node/Service/Type', attributes: {{...}}}}]\n"
            f"- relations: [{{source: 'xxx', target: 'yyy', type: 'contains/extends/implements'}}]\n"
            f"- parent_map: {{'node_id': 'parent_node_id'}}\n"
            f"严格输出JSON，不要包含其他文字。"
        )
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "你是架构分析专家。请提取结构化数据，严格按照指定格式输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(self.lm_studio_url, json=payload, timeout=600)
            response.raise_for_status()
            result_text = response.json()['choices'][0]['message']['content']
            
            result_text = self._clean_json_output(result_text)
            return json.loads(result_text)
        except Exception as e:
            print(f"Error during parsing chunk: {e}")
            return None
    
    def _clean_json_output(self, text: str) -> str:
        """清理模型返回的JSON"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# --- OPCUAParser 主解析器 ---
class ProjectParser:
    """主解析器 - 整合Parser、Notebook和ReasoningEngine"""
    
    def __init__(self, source_file: str, notebook_file: str, config: Dict[str, Any]):
        self.parser = TextParser(source_file)
        self.notebook = Notebook(notebook_file)
        self.engine = ReasoningEngine(
            config["lm_studio_url"],
            config["model_name"],
            config["temperature"],
            config["max_tokens"]
        )
        self.chunk_size = config["chunk_size"]
    
    def run(self):
        """主循环：逐块读取并更新记忆"""
        lines = self.parser.read_lines()
        print(f"Total lines in file: {len(lines)}")
        
        if self.notebook.memory["parsed_lines"]:
            print(f"Resuming from line {max(self.notebook.memory['parsed_lines']) + 1}")
            start_idx = max(self.notebook.memory["parsed_lines"]) - 1
            lines = lines[start_idx:]
        else:
            print("Starting fresh parse...")
        
        chunks = self.parser.chunk_lines(lines, self.chunk_size)
        print(f"Total chunks to process: {len(chunks)}")
        
        for chunk_idx, chunk in enumerate(chunks, 1):
            print(f"\nProcessing chunk {chunk_idx}/{len(chunks)}...")
            
            context_snippet = self.notebook.retrieve_relevant_context(chunk)
            print(f"Retrieved relevant context: {len(context_snippet)} chars")
            
            new_knowledge = self.engine.call_lm_studio(chunk, context_snippet)
            
            if new_knowledge:
                self._update_memory(new_knowledge)
                line_start = (chunk_idx - 1) * self.chunk_size + 1
                line_end = min(chunk_idx * self.chunk_size, len(lines))
                self.notebook.update_parsed_lines(list(range(line_start, line_end + 1)))
                self.notebook.update_summary()
                print("Chunk processed and memory updated.")
            else:
                print("Failed to parse chunk, skipping...")
    
    def _update_memory(self, new_data: Dict[str, Any]):
        """合并新知识到笔记本"""
        added_entities = 0
        added_relations = 0
        
        if "entities" in new_data:
            for ent in new_data["entities"]:
                if self.notebook.add_entity(ent):
                    added_entities += 1
        
        if "relations" in new_data:
            for rel in new_data["relations"]:
                if self.notebook.add_relation(rel):
                    added_relations += 1
        
        if "parent_map" in new_data:
            for node_id, parent_id in new_data["parent_map"].items():
                self.notebook.add_parent_mapping(node_id, parent_id)
        
        print(f"Added {added_entities} entities, {added_relations} relations")
    
    def get_statistics(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "entities": len(self.notebook.memory["entities"]),
            "relations": len(self.notebook.memory["relations"]),
            "parent_map_entries": len(self.notebook.memory["parent_map"]),
            "parsed_lines": len(self.notebook.memory["parsed_lines"])
        }


# --- 项目架构生成 ---
def get_folder_structure(selected_dir, output_dir=None):
    """
    生成项目架构文件
    :param selected_dir: 用户选择的目标文件夹
    :param output_dir: 输出目录，默认为当前项目目录
    :return: 生成的架构文件路径
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    
    folder_name = os.path.basename(selected_dir)
    output_file = os.path.join(output_dir, f"{folder_name}_架构.txt")
    
    print(f"正在生成项目架构...")
    print(f"目标文件夹: {selected_dir}")
    print(f"输出文件: {output_file}")
    
    structure = []
    for root, dirs, files in os.walk(selected_dir):
        rel_path = os.path.relpath(root, selected_dir)
        level = rel_path.count(os.sep) if rel_path != '.' else 0
        indent = '│   ' * (level) + '├── ' if level > 0 else ''
        structure.append(f"{indent}{os.path.basename(root)}/")
        
        sub_indent = '│   ' * (level + 1) + '├── '
        for f in files:
            structure.append(f"{sub_indent}{f}")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(structure))
    
    target_ext = {
        '.c', '.cpp', '.h', '.hpp', '.java', '.py', '.js', '.php', 
        '.rb', '.swift', '.go', '.kt', '.scala', '.cs', '.ts', '.tsx',
        '.vue', '.jsx', '.asm', '.r', '.pl', '.lua', '.sh', '.bash',
        '.bat', '.cmd', '.ps1', '.ini', '.json', '.yaml', '.yml', '.xml',
        '.conf', '.cfg', '.properties', '.html', '.htm', '.css', '.scss',
        '.less', '.sql', '.md', '.gitignore'
    }
    current_script = os.path.abspath(__file__)
    
    with open(output_file, 'a', encoding='utf-8') as out_f:
        for root, _, files in os.walk(selected_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.stat().st_size > 1024 * 1024:
                    continue
                if file_path.suffix.lower() in target_ext:
                    if str(file_path.resolve()) != os.path.abspath(current_script):
                        rel_path = file_path.relative_to(selected_dir)
                        out_f.write(f"\n\n─── {rel_path} ───\n")
                        try:
                            with open(file_path, 'rb') as in_f:
                                content = in_f.read()
                                if b'\x00' in content:
                                    raise UnicodeDecodeError('binary', b'', 0, 0, '')
                                text_content = content.decode('utf-8')
                            out_f.write(text_content)
                        except (UnicodeDecodeError, PermissionError):
                            out_f.write(f"已跳过非文本文件：{file_path.name}")
                        except Exception as e:
                            out_f.write(f"文件读取失败：{str(e)}")
    
    print(f"架构文件生成完成！")
    return output_file


# --- 增量学习执行 ---
def run_incremental_learning(source_file):
    """
    调用增量学习解析器处理生成的架构文件
    """
    try:
        notebook_file = source_file.replace("_架构.txt", "_memory.json")
        
        parser = ProjectParser(source_file, notebook_file, DEFAULT_CONFIG)
        parser.run()
        
        stats = parser.get_statistics()
        print("\n" + "=" * 60)
        print("增量学习完成！")
        print(f"实体数量: {stats['entities']}")
        print(f"关系数量: {stats['relations']}")
        print(f"层级映射: {stats['parent_map_entries']}")
        print(f"已解析行数: {stats['parsed_lines']}")
        print("=" * 60)
        
        return True
    except Exception as e:
        print(f"增量学习过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


# --- 主入口 ---
def main():
    root = tk.Tk()
    root.withdraw()
    
    initial_dir = os.path.dirname(os.path.abspath(__file__))
    
    selected_dir = filedialog.askdirectory(
        title='请选择要分析的项目文件夹',
        initialdir=initial_dir
    )
    
    if not selected_dir:
        messagebox.showinfo("提示", "操作已取消")
        return
    
    try:
        output_file = get_folder_structure(selected_dir)
        
        result = messagebox.askyesno(
            "增量学习",
            f"架构文件已生成：\n{output_file}\n\n是否进行增量学习？"
        )
        
        if result:
            success = run_incremental_learning(output_file)
            if success:
                messagebox.showinfo("完成", "增量学习已完成！")
            else:
                messagebox.showwarning("警告", "增量学习未完成，请检查 LM Studio 是否运行")
        
    except Exception as e:
        messagebox.showerror("错误", f"发生错误：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()