import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import filedialog, messagebox


SUPPORTED_EXTENSIONS = ['.txt', '.md', '.pdf', '.json', '.xml', '.html', '.htm']

DOCUMENT_TYPE_TEXTBOOK = "textbook"
DOCUMENT_TYPE_NOVEL = "novel"
DOCUMENT_TYPE_PAPER = "paper"

DOCUMENT_TYPES = [
    (DOCUMENT_TYPE_TEXTBOOK, "教材/技术文档"),
    (DOCUMENT_TYPE_NOVEL, "小说/文学"),
    (DOCUMENT_TYPE_PAPER, "学术论文")
]


def load_config(config_file: str = "config.json") -> Dict[str, Any]:
    default_config = {
        "lm_studio_url": "http://localhost:1234/v1/chat/completions",
        "model_name": "gemma-4-26b-a4b-it-uncensored",
        "chunk_size": 5,
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


TEXTBOOK_PROMPT = """## Context from previous reading (已有的知识):
{context}

## New text to analyze (新文本):
{chunk}

## Task (任务):
分析这段教材/技术文档内容，提取知识图谱：

1. **实体(entities)**: 核心概念/定义、对象/实体、方法/原理、公式/定理、示例/案例
2. **关系(relations)**:
   - 包含关系：概念之间的层级包含（如"操作系统 包含 进程管理"）
   - 因果关系：原理与结果（如"CPU调度 → 系统吞吐量"）
   - 组成关系：整体与部分（如"计算机 → CPU、内存、I/O设备"）
   - 关联关系：相关但非直接包含或因果
3. **parent_map**: 上位概念与下位概念的映射

## Output Format (输出格式):
请输出JSON格式，包含以下字段：
- entities: [{{name: 'xxx', type: '概念/对象/方法/公式/示例', attributes: {{description: '...', importance: 'high/medium/low'}}}}]
- relations: [{{source: 'xxx', target: 'yyy', type: '包含/因果/组成/关联'}}]
- parent_map: {{'下位概念': '上位概念'}}
严格输出JSON，不要包含其他文字。"""

NOVEL_PROMPT = """## Context from previous reading (已有的知识):
{context}

## New text to analyze (新文本):
{chunk}

## Task (任务):
分析这段小说/文学文本，提取知识图谱：

1. **实体(entities)**: 人物、地点、时间、事件、物品/道具、主题/意象
2. **关系(relations)**:
   - 社会关系：人物之间的关系（亲情/友情/爱情/敌对/从属）
   - 因果关系：事件之间的因果链
   - 时序关系：事件发生的时间顺序
   - 主题关联：与核心主题的关联
3. **parent_map**: 场景/章节与上下文的映射

实体属性应包含：
- 人物：age（年龄）, personality（性格）, role（角色定位）, evaluation（他人评价）, psychology（心理归因）
- 地点：setting（场景设定）, significance（意义）
- 事件：timeline（时间线位置）, social_background（社会背景）, cultural_context（文化背景）

## Output Format (输出格式):
请输出JSON格式，包含以下字段：
- entities: [{{name: 'xxx', type: '人物/地点/时间/事件/物品/主题', attributes: {{age/personality/setting/...}}}}]
- relations: [{{source: 'xxx', target: 'yyy', type: '亲情/友情/爱情/敌对/因果/时序/主题'}}]
- parent_map: {{'子实体': '父实体'}}
严格输出JSON，不要包含其他文字。"""

SYSTEM_PROMPTS = {
    DOCUMENT_TYPE_TEXTBOOK: "你是一位知识整理专家，擅长从教材和技术文档中提取结构化的知识体系。",
    DOCUMENT_TYPE_NOVEL: "你是一位文学分析专家，擅长分析小说的人物关系、情节发展和主题意涵。",
    DOCUMENT_TYPE_PAPER: "你是一位学术研究助手，擅长分析学术论文的研究方法、理论框架和实验结论。"
}

PAPER_PROMPT = """## Context from previous reading (已有的知识):
{context}

## New text to analyze (新文本):
{chunk}

## Task (任务):
分析这段学术论文内容，提取知识图谱：

1. **实体(entities)**: 研究问题/假设、理论/模型、方法/技术、实验/数据、结论/发现、文献/引用
2. **关系(relations)**:
   - 理论支撑：理论框架与研究假设的关系
   - 方法应用：使用的方法与技术
   - 因果关系：实验条件与结果发现
   - 引用关系：与前人研究的关系
   - 对比关系：与同类研究的对比
3. **parent_map**: 研究流程中各环节的层级关系

实体属性应包含：
- 研究问题：novelty（创新点）, significance（重要性）
- 方法：type（实验/建模/分析）, scope（适用范围）
- 结论：confidence（置信度）, limitation（局限性）
- 引用：year（年份）, venue（发表 venue）

## Output Format (输出格式):
请输出JSON格式，包含以下字段：
- entities: [{{name: 'xxx', type: '研究问题/理论/方法/实验/结论/引用', attributes: {{novelty/scope/confidence/...}}}}]
- relations: [{{source: 'xxx', target: 'yyy', type: '理论支撑/方法应用/因果/引用/对比'}}]
- parent_map: {{'子环节': '父环节'}}
严格输出JSON，不要包含其他文字。"""


class Notebook:
    def __init__(self, notebook_file: str, doc_type: str = DOCUMENT_TYPE_TEXTBOOK):
        self.notebook_file = notebook_file
        self.doc_type = doc_type
        self.memory = self._load_notebook()

    def _load_notebook(self) -> Dict[str, Any]:
        if os.path.exists(self.notebook_file):
            try:
                with open(self.notebook_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if loaded.get("doc_type") == self.doc_type:
                        return loaded
            except:
                print(f"Warning: Failed to load {self.notebook_file}, starting fresh")
        return {
            "doc_type": self.doc_type,
            "entities": [],
            "relations": [],
            "parent_map": {},
            "parsed_chunks": [],
            "summary": "",
            "metadata": {}
        }

    def _save_notebook(self):
        with open(self.notebook_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=4)

    def add_entity(self, entity: Dict[str, Any]) -> bool:
        entity_key = self._get_entity_key(entity)
        existing_keys = [self._get_entity_key(e) for e in self.memory["entities"]]
        if entity_key not in existing_keys:
            self.memory["entities"].append(entity)
            self._save_notebook()
            return True
        return False

    def add_relation(self, relation: Dict[str, Any]) -> bool:
        relation_key = self._get_relation_key(relation)
        existing_keys = [self._get_relation_key(r) for r in self.memory["relations"]]
        if relation_key not in existing_keys:
            self.memory["relations"].append(relation)
            self._save_notebook()
            return True
        return False

    def add_parent_mapping(self, node_id: str, parent_id: str):
        if node_id not in self.memory["parent_map"]:
            self.memory["parent_map"][node_id] = parent_id
            self._save_notebook()

    def update_parsed_chunks(self, chunk_indices: List[int]):
        for idx in chunk_indices:
            if idx not in self.memory["parsed_chunks"]:
                self.memory["parsed_chunks"].append(idx)
        self.memory["parsed_chunks"] = sorted(list(set(self.memory["parsed_chunks"])))
        self._save_notebook()

    def update_summary(self):
        entity_names = [e.get("name", "") for e in self.memory["entities"]]
        relation_count = len(self.memory["relations"])
        self.memory["summary"] = (
            f"[{self._get_doc_type_name()}] "
            f"已识别 {len(self.memory['entities'])} 个实体: {', '.join(entity_names[:10])}..."
            f"\n已识别 {relation_count} 个关系"
        )
        self._save_notebook()

    def _get_doc_type_name(self) -> str:
        for doc_type, name in DOCUMENT_TYPES:
            if doc_type == self.doc_type:
                return name
        return "未知"

    def _get_entity_key(self, entity: Dict[str, Any]) -> str:
        name = entity.get("name", "").lower()
        node_id = entity.get("node_id", "").lower()
        return f"{name}|{node_id}"

    def _get_relation_key(self, relation: Dict[str, Any]) -> str:
        source = relation.get("source", "").lower()
        target = relation.get("target", "").lower()
        rel_type = relation.get("type", "").lower()
        return f"{source}|{target}|{rel_type}"

    def retrieve_relevant_context(self, current_chunk: str, max_items: int = 5) -> str:
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


class DocumentParser:
    def __init__(self, source_file: str):
        self.source_file = source_file
        self.extension = Path(source_file).suffix.lower()

    def read_content(self) -> List[str]:
        if self.extension == '.txt' or self.extension == '.md':
            return self._read_text()
        elif self.extension == '.pdf':
            return self._read_pdf()
        elif self.extension == '.json':
            return self._read_json()
        elif self.extension == '.xml':
            return self._read_xml()
        elif self.extension == '.html' or self.extension == '.htm':
            return self._read_html()
        else:
            return self._read_text()

    def _read_text(self) -> List[str]:
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
        for encoding in encodings:
            try:
                with open(self.source_file, 'r', encoding=encoding) as f:
                    return f.readlines()
            except UnicodeDecodeError:
                continue
        print(f"无法解码文件 {self.source_file}，尝试二进制读取")
        with open(self.source_file, 'rb') as f:
            content = f.read()
            try:
                return content.decode('utf-8', errors='replace').splitlines(keepends=True)
            except:
                return [content.decode('utf-8', errors='replace')]

    def _read_pdf(self) -> List[str]:
        try:
            import PyPDF2
            lines = []
            with open(self.source_file, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        lines.append(f"[页面 {page_num + 1}]\n{text}\n")
            return lines
        except ImportError:
            print("请安装 PyPDF2: pip install PyPDF2")
            return []
        except Exception as e:
            print(f"PDF读取失败: {e}")
            return []

    def _read_json(self) -> List[str]:
        with open(self.source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [json.dumps(data, ensure_ascii=False, indent=2)]

    def _read_xml(self) -> List[str]:
        import xml.etree.ElementTree as ET
        tree = ET.parse(self.source_file)
        lines = []
        for elem in tree.iter():
            if elem.text and elem.text.strip():
                lines.append(f"<{elem.tag}>{elem.text}</{elem.tag}>\n")
        return lines

    def _read_html(self) -> List[str]:
        try:
            from bs4 import BeautifulSoup
            with open(self.source_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            return [soup.get_text()]
        except ImportError:
            print("请安装 bs4: pip install bs4")
            return []
        except Exception as e:
            print(f"HTML读取失败: {e}")
            return []

    def chunk_content(self, content: List[str], chunk_size: int = 5) -> List[str]:
        chunks = []
        for i in range(0, len(content), chunk_size):
            chunk = "".join(content[i:i+chunk_size])
            chunks.append(chunk)
        return chunks


class ReasoningEngine:
    def __init__(self, lm_studio_url: str, model_name: str, doc_type: str = DOCUMENT_TYPE_TEXTBOOK,
                 temperature: float = 0.1, max_tokens: int = 2048):
        self.lm_studio_url = lm_studio_url
        self.model_name = model_name
        self.doc_type = doc_type
        self.temperature = temperature
        self.max_tokens = max_tokens

    def call_lm_studio(self, current_chunk: str, context_from_notebook: str) -> Optional[Dict[str, Any]]:
        if self.doc_type == DOCUMENT_TYPE_TEXTBOOK:
            template = TEXTBOOK_PROMPT
        elif self.doc_type == DOCUMENT_TYPE_NOVEL:
            template = NOVEL_PROMPT
        else:
            template = PAPER_PROMPT
        prompt = template.format(context=context_from_notebook, chunk=current_chunk)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPTS.get(self.doc_type, SYSTEM_PROMPTS[DOCUMENT_TYPE_TEXTBOOK])},
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
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


class BookParser:
    def __init__(self, source_file: str, notebook_file: str, doc_type: str, config: Dict[str, Any]):
        self.parser = DocumentParser(source_file)
        self.notebook = Notebook(notebook_file, doc_type)
        self.engine = ReasoningEngine(
            config["lm_studio_url"],
            config["model_name"],
            doc_type,
            config["temperature"],
            config["max_tokens"]
        )
        self.chunk_size = config["chunk_size"]
        self.doc_type = doc_type

    def run(self):
        content = self.parser.read_content()
        if not content:
            print("无法读取文档内容")
            return

        print(f"Total lines in document: {len(content)}")

        if self.notebook.memory["parsed_chunks"]:
            print(f"Resuming from chunk {max(self.notebook.memory['parsed_chunks']) + 1}")
            start_idx = max(self.notebook.memory["parsed_chunks"]) + 1
            content = content[start_idx * self.chunk_size:]
        else:
            print("Starting fresh reading...")

        chunks = self.parser.chunk_content(content, self.chunk_size)
        print(f"Total chunks to process: {len(chunks)}")

        for chunk_idx, chunk in enumerate(chunks, 1):
            print(f"\nProcessing chunk {chunk_idx}/{len(chunks)}...")

            context_snippet = self.notebook.retrieve_relevant_context(chunk)
            print(f"Retrieved relevant context: {len(context_snippet)} chars")

            new_knowledge = self.engine.call_lm_studio(chunk, context_snippet)

            if new_knowledge:
                self._update_memory(new_knowledge)
                self.notebook.update_parsed_chunks([chunk_idx])
                self.notebook.update_summary()
                print("Chunk processed and memory updated.")
            else:
                print("Failed to parse chunk, skipping...")

    def _update_memory(self, new_data: Dict[str, Any]):
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
        return {
            "entities": len(self.notebook.memory["entities"]),
            "relations": len(self.notebook.memory["relations"]),
            "parent_map_entries": len(self.notebook.memory["parent_map"]),
            "parsed_chunks": len(self.notebook.memory["parsed_chunks"])
        }

    def export_knowledge_graph(self, output_file: str):
        doc_type_names = {
            DOCUMENT_TYPE_TEXTBOOK: "教材/技术文档",
            DOCUMENT_TYPE_NOVEL: "小说/文学",
            DOCUMENT_TYPE_PAPER: "学术论文"
        }
        doc_type_name = doc_type_names.get(self.doc_type, "未知")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 知识图谱 ({doc_type_name})\n\n")

            if self.doc_type == DOCUMENT_TYPE_TEXTBOOK:
                self._export_textbook_format(f)
            elif self.doc_type == DOCUMENT_TYPE_NOVEL:
                self._export_novel_format(f)
            else:
                self._export_paper_format(f)

    def _export_textbook_format(self, f):
        entities_by_type = {}
        for entity in self.notebook.memory["entities"]:
            ent_type = entity.get('type', '其他')
            if ent_type not in entities_by_type:
                entities_by_type[ent_type] = []
            entities_by_type[ent_type].append(entity)

        f.write(f"## 概念与定义 (共 {len(self.notebook.memory['entities'])} 个)\n\n")
        for ent_type, entities in entities_by_type.items():
            f.write(f"### {ent_type}\n")
            for entity in entities:
                name = entity.get('name', '')
                attrs = entity.get('attributes', {})
                importance = attrs.get('importance', '') if isinstance(attrs, dict) else ''
                desc = attrs.get('description', '') if isinstance(attrs, dict) else ''
                imp_mark = f"[{importance.upper()}]" if importance else ""
                f.write(f"- **{name}** {imp_mark}")
                if desc:
                    f.write(f": {desc}")
                f.write("\n")
            f.write("\n")

        f.write(f"## 知识关系 (共 {len(self.notebook.memory['relations'])} 个)\n\n")
        for relation in self.notebook.memory["relations"]:
            source = relation.get('source', '')
            target = relation.get('target', '')
            rel_type = relation.get('type', '')
            arrow = self._get_relation_arrow(rel_type)
            f.write(f"- {source} {arrow} {target}\n")

        if self.notebook.memory["parent_map"]:
            f.write(f"\n## 概念层级\n\n")
            for node_id, parent_id in self.notebook.memory["parent_map"].items():
                f.write(f"- {node_id} ⊂ {parent_id}\n")

    def _export_novel_format(self, f):
        entities_by_type = {}
        for entity in self.notebook.memory["entities"]:
            ent_type = entity.get('type', '其他')
            if ent_type not in entities_by_type:
                entities_by_type[ent_type] = []
            entities_by_type[ent_type].append(entity)

        f.write(f"## 人物 (共 {len(entities_by_type.get('人物', []))} 个)\n\n")
        for entity in entities_by_type.get('人物', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                personality = attrs.get('personality', '')
                evaluation = attrs.get('evaluation', '')
                psychology = attrs.get('psychology', '')
                f.write(f"- **{name}**\n")
                if personality:
                    f.write(f"  - 性格: {personality}\n")
                if evaluation:
                    f.write(f"  - 评价: {evaluation}\n")
                if psychology:
                    f.write(f"  - 心理: {psychology}\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 地点与场景 (共 {len(entities_by_type.get('地点', []))} 个)\n\n")
        for entity in entities_by_type.get('地点', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            setting = attrs.get('setting', '') if isinstance(attrs, dict) else ''
            f.write(f"- **{name}**")
            if setting:
                f.write(f": {setting}")
            f.write("\n")

        f.write(f"\n## 事件时间线 (共 {len(entities_by_type.get('事件', []))} 个)\n\n")
        for entity in entities_by_type.get('事件', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                timeline = attrs.get('timeline', '')
                social_bg = attrs.get('social_background', '')
                cultural_ctx = attrs.get('cultural_context', '')
                f.write(f"- **{name}**")
                if timeline:
                    f.write(f" [{timeline}]")
                f.write("\n")
                if social_bg:
                    f.write(f"  - 社会背景: {social_bg}\n")
                if cultural_ctx:
                    f.write(f"  - 文化背景: {cultural_ctx}\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 人物关系 (共 {len(self.notebook.memory['relations'])} 个)\n\n")
        for relation in self.notebook.memory["relations"]:
            source = relation.get('source', '')
            target = relation.get('target', '')
            rel_type = relation.get('type', '')
            arrow = self._get_novel_relation_arrow(rel_type)
            f.write(f"- {source} {arrow} {target}\n")

        if self.notebook.memory["parent_map"]:
            f.write(f"\n## 场景层级\n\n")
            for node_id, parent_id in self.notebook.memory["parent_map"].items():
                f.write(f"- {node_id} ⊂ {parent_id}\n")

    def _export_paper_format(self, f):
        entities_by_type = {}
        for entity in self.notebook.memory["entities"]:
            ent_type = entity.get('type', '其他')
            if ent_type not in entities_by_type:
                entities_by_type[ent_type] = []
            entities_by_type[ent_type].append(entity)

        f.write(f"## 研究问题与假设 (共 {len(entities_by_type.get('研究问题', []))} 个)\n\n")
        for entity in entities_by_type.get('研究问题', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                novelty = attrs.get('novelty', '')
                significance = attrs.get('significance', '')
                f.write(f"- **{name}**\n")
                if novelty:
                    f.write(f"  - 创新点: {novelty}\n")
                if significance:
                    f.write(f"  - 重要性: {significance}\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 理论框架 (共 {len(entities_by_type.get('理论', []))} 个)\n\n")
        for entity in entities_by_type.get('理论', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            scope = attrs.get('scope', '') if isinstance(attrs, dict) else ''
            f.write(f"- **{name}**")
            if scope:
                f.write(f": 适用范围 - {scope}")
            f.write("\n")

        f.write(f"\n## 研究方法 (共 {len(entities_by_type.get('方法', []))} 个)\n\n")
        for entity in entities_by_type.get('方法', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                method_type = attrs.get('type', '')
                scope = attrs.get('scope', '')
                f.write(f"- **{name}**")
                if method_type:
                    f.write(f" [{method_type}]")
                if scope:
                    f.write(f": 适用范围 - {scope}")
                f.write("\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 实验与数据 (共 {len(entities_by_type.get('实验', []))} 个)\n\n")
        for entity in entities_by_type.get('实验', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                dataset = attrs.get('dataset', '')
                f.write(f"- **{name}**")
                if dataset:
                    f.write(f": 数据集 - {dataset}")
                f.write("\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 研究结论 (共 {len(entities_by_type.get('结论', []))} 个)\n\n")
        for entity in entities_by_type.get('结论', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            if isinstance(attrs, dict):
                confidence = attrs.get('confidence', '')
                limitation = attrs.get('limitation', '')
                f.write(f"- **{name}**")
                if confidence:
                    f.write(f" [置信度: {confidence}]")
                f.write("\n")
                if limitation:
                    f.write(f"  - 局限性: {limitation}\n")
            else:
                f.write(f"- **{name}**\n")

        f.write(f"\n## 引用文献 (共 {len(entities_by_type.get('引用', []))} 个)\n\n")
        for entity in entities_by_type.get('引用', []):
            name = entity.get('name', '')
            attrs = entity.get('attributes', {})
            year = attrs.get('year', '') if isinstance(attrs, dict) else ''
            venue = attrs.get('venue', '') if isinstance(attrs, dict) else ''
            f.write(f"- **{name}**")
            if year:
                f.write(f" ({year})")
            if venue:
                f.write(f": {venue}")
            f.write("\n")

        f.write(f"\n## 研究关系 (共 {len(self.notebook.memory['relations'])} 个)\n\n")
        for relation in self.notebook.memory["relations"]:
            source = relation.get('source', '')
            target = relation.get('target', '')
            rel_type = relation.get('type', '')
            arrow = self._get_paper_relation_arrow(rel_type)
            f.write(f"- {source} {arrow} {target}\n")

        if self.notebook.memory["parent_map"]:
            f.write(f"\n## 研究流程\n\n")
            for node_id, parent_id in self.notebook.memory["parent_map"].items():
                f.write(f"- {node_id} ⊂ {parent_id}\n")

    def _get_relation_arrow(self, rel_type: str) -> str:
        arrows = {
            "包含": "→",
            "因果": "⇒",
            "组成": "＋",
            "关联": "↔"
        }
        return arrows.get(rel_type, "—")

    def _get_novel_relation_arrow(self, rel_type: str) -> str:
        arrows = {
            "亲情": "❤️",
            "友情": "🤝",
            "爱情": "💕",
            "敌对": "⚔️",
            "从属": "→",
            "因果": "⇒",
            "时序": "→",
            "主题": "✦"
        }
        return arrows.get(rel_type, "—")

    def _get_paper_relation_arrow(self, rel_type: str) -> str:
        arrows = {
            "理论支撑": "⊢",
            "方法应用": "⚙️",
            "因果": "⇒",
            "引用": "📚",
            "对比": "↔",
            "验证": "✓"
        }
        return arrows.get(rel_type, "→")


def run_book_learning(source_file: str, doc_type: str):
    try:
        base_name = Path(source_file).stem
        doc_type_suffix_map = {
            DOCUMENT_TYPE_TEXTBOOK: "教材",
            DOCUMENT_TYPE_NOVEL: "小说",
            DOCUMENT_TYPE_PAPER: "论文"
        }
        doc_type_suffix = doc_type_suffix_map.get(doc_type, "未知")
        notebook_file = os.path.join(os.path.dirname(source_file), f"{base_name}_{doc_type_suffix}_knowledge.json")

        parser = BookParser(source_file, notebook_file, doc_type, DEFAULT_CONFIG)
        parser.run()

        stats = parser.get_statistics()
        print("\n" + "=" * 60)
        print(f"读书学习完成！({parser.notebook._get_doc_type_name()})")
        print(f"实体数量: {stats['entities']}")
        print(f"关系数量: {stats['relations']}")
        print(f"层级映射: {stats['parent_map_entries']}")
        print(f"已解析块数: {stats['parsed_chunks']}")
        print("=" * 60)

        return True, parser
    except Exception as e:
        print(f"读书学习过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def main():
    import argparse

    parser = argparse.ArgumentParser(description='读书助手 - 文档知识图谱构建工具')
    parser.add_argument('type', nargs='?', choices=['textbook', 'novel', 'paper'],
                        help='文档类型: textbook(教材) / novel(小说) / paper(论文)')
    parser.add_argument('file', nargs='?', help='要分析的文件路径')
    args = parser.parse_args()

    if not args.type:
        print("用法: python 读书助手.py <textbook|novel|paper> [文件路径]")
        print("  python 读书助手.py textbook sample.txt")
        print("  python 读书助手.py novel story.md")
        print("  python 读书助手.py paper research.pdf")
        return

    doc_type_map = {
        'textbook': DOCUMENT_TYPE_TEXTBOOK,
        'novel': DOCUMENT_TYPE_NOVEL,
        'paper': DOCUMENT_TYPE_PAPER
    }
    doc_type = doc_type_map[args.type]

    if not args.file:
        root = tk.Tk()
        root.withdraw()

        file_types = [
            ("文本文件 (*.txt)", "*.txt"),
            ("Markdown文件 (*.md)", "*.md"),
            ("PDF文件 (*.pdf)", "*.pdf"),
            ("JSON文件 (*.json)", "*.json"),
            ("XML文件 (*.xml)", "*.xml"),
            ("HTML文件 (*.html)", "*.html"),
            ("所有支持的文件", "*.txt *.md *.pdf *.json *.xml *.html *.htm")
        ]

        selected_file = filedialog.askopenfilename(
            title=f'请选择要阅读的文档 (类型: {args.type})',
            initialdir=os.path.dirname(os.path.abspath(__file__)),
            filetypes=file_types
        )

        if not selected_file:
            messagebox.showinfo("提示", "操作已取消")
            return
    else:
        selected_file = args.file

    file_ext = Path(selected_file).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        print(f"错误: 不支持的文件格式 {file_ext}")
        print(f"支持的格式: {', '.join(SUPPORTED_EXTENSIONS)}")
        return

    try:
        doc_type_names = {
            DOCUMENT_TYPE_TEXTBOOK: "教材/技术文档",
            DOCUMENT_TYPE_NOVEL: "小说/文学",
            DOCUMENT_TYPE_PAPER: "学术论文"
        }
        doc_type_suffix_map = {
            DOCUMENT_TYPE_TEXTBOOK: "教材",
            DOCUMENT_TYPE_NOVEL: "小说",
            DOCUMENT_TYPE_PAPER: "论文"
        }
        doc_type_name = doc_type_names.get(doc_type, "未知")
        doc_type_suffix = doc_type_suffix_map.get(doc_type, "未知")
        result, book_parser = run_book_learning(selected_file, doc_type)

        if result and book_parser:
            export_file = selected_file.replace(Path(selected_file).suffix, f"_{doc_type_suffix}_知识图谱.md")
            book_parser.export_knowledge_graph(export_file)

            response = messagebox.askyesno(
                "完成",
                f"[{doc_type_name}] 知识图谱已生成：\n{export_file}\n\n是否查看知识图谱内容？"
            )

            if response:
                messagebox.showinfo("知识图谱摘要", book_parser.notebook.memory["summary"])
        else:
            messagebox.showwarning("警告", "读书学习未完成，请检查 LM Studio 是否运行")

    except Exception as e:
        messagebox.showerror("错误", f"发生错误：{str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
