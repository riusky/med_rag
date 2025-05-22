# 混合分块 (Hybrid Chunking)

# 首先尝试基于文档结构（如 Markdown 标题）进行高级别分割，
# 然后在这些较大的分割块内部，如果它们仍然超过了目标大小，
# 再使用递归字符分块或句子分块进行细粒度的切分。


import yaml
import re
import copy
from typing import (Dict, List, Optional, Tuple, TypedDict, Callable, Union) # 添加 Union
from dataclasses import dataclass, field
from prefect import task, get_run_logger
from langchain.schema import Document
# --- 数据结构和类型定义 ---

@dataclass
class Chunk:
    """用于存储文本片段及相关元数据的类。"""
    content: str = ''
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """重写 __str__ 方法，使其仅包含 content 和 metadata。"""
        if self.metadata:
            return f"content='{self.content}' metadata={self.metadata}"
        else:
            return f"content='{self.content}'"

    def __repr__(self) -> str:
        return self.__str__()

    def to_markdown(self, return_all: bool = False) -> str:
        """将块转换为 Markdown 格式。

        Args:
            return_all: 如果为 True，则在内容前包含 YAML 格式的元数据。

        Returns:
            Markdown 格式的字符串。
        """
        md_string = ""
        if return_all and self.metadata:
            # 使用 yaml.dump 将元数据格式化为 YAML 字符串
            # allow_unicode=True 确保中文字符正确显示
            # sort_keys=False 保持原始顺序
            metadata_yaml = yaml.dump(self.metadata, allow_unicode=True, sort_keys=False)
            md_string += f"---\n{metadata_yaml}---\n\n"
        md_string += self.content
        return md_string
      
    # 转换函数
    def to_document(self) -> Document:
        """将单个 Chunk 转换为 Document"""
        return Document(
            page_content=self.to_markdown(return_all=True),  # 包含元数据头的完整格式
            metadata=self.metadata.copy()
        )
        
    @staticmethod
    def chunks_to_documents(chunks: List['Chunk']) -> List[Document]:
        """静态方法：批量转换 Chunk 列表"""
        return [chunk.to_document() for chunk in chunks]
        
class LineType(TypedDict):
    """行类型，使用类型字典定义。"""
    metadata: Dict[str, str] # 元数据字典
    content: str # 行内容

class HeaderType(TypedDict):
    """标题类型，使用类型字典定义。"""
    level: int # 标题级别
    name: str # 标题名称 (例如, 'Header 1')
    data: str # 标题文本内容

class MarkdownHeaderTextSplitter:
    """基于指定的标题分割 Markdown 文件，并可选地根据 chunk_size 进一步细分。"""

    def __init__(
        self,
        headers_to_split_on: List[Tuple[str, str]] = [
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
            ("####", "h4"),
            ("#####", "h5"),
            ("######", "h6"),
        ],
        strip_headers: bool = False,
        chunk_size: Optional[int] = None, # 添加 chunk_size 参数
        length_function: Callable[[str], int] = len, # 添加 length_function 参数
        separators: Optional[List[str]] = None, # 添加 separators 参数
        is_separator_regex: bool = False, # 添加 is_separator_regex 参数
    ):
        """创建一个新的 MarkdownHeaderTextSplitter。

        Args:
            headers_to_split_on: 用于分割的标题级别和名称元组列表。
            strip_headers: 是否从块内容中移除标题行。
            chunk_size: 块的最大非代码内容长度。如果设置，将进一步分割超出的块。
            length_function: 用于计算文本长度的函数。
            separators: 用于分割的分隔符列表，优先级从高到低。
            is_separator_regex: 是否将分隔符视为正则表达式。
        """
        if chunk_size is not None and chunk_size <= 0:
            raise ValueError("chunk_size 必须是正整数或 None。")

        self.headers_to_split_on = sorted(
            headers_to_split_on, key=lambda split: len(split[0]), reverse=True
        )
        self.strip_headers = strip_headers
        self._chunk_size = chunk_size
        self._length_function = length_function
        # 设置默认分隔符，优先段落，其次换行
        self._separators = separators or [
            "\n\n",  # 段落
            "\n",    # 行
            "。|！|？",  # 中文句末标点
            r"\.\s|\!\s|\?\s", # 英文句末标点加空格
            r"；|;\s",  # 分号
            r"，|,\s"   # 逗号
        ]
        self._is_separator_regex = is_separator_regex
        # 预编译正则表达式（如果需要）
        self._compiled_separators = None
        if self._is_separator_regex:
            self._compiled_separators = [re.compile(s) for s in self._separators]

    def _calculate_length_excluding_code(self, text: str) -> int:
        """计算文本长度，不包括代码块内容。"""
        total_length = 0
        last_end = 0
        # 正则表达式查找 ```...``` 或 ~~~...~~~ 代码块
        # 使用非贪婪匹配 .*?
        for match in re.finditer(r"(?:```|~~~).*?\n(?:.*?)(?:```|~~~)", text, re.DOTALL | re.MULTILINE):
            start, end = match.span()
            # 添加此代码块之前的文本长度
            total_length += self._length_function(text[last_end:start])
            last_end = end
        # 添加最后一个代码块之后的文本长度
        total_length += self._length_function(text[last_end:])
        return total_length

    def _find_best_split_point(self, lines: List[str]) -> int:
        """在行列表中查找最佳分割点（索引）。

        优先寻找段落分隔符（连续两个换行符），其次是单个换行符。
        从后向前查找，返回分割点 *之后* 的那一行索引。
        如果找不到合适的分隔点（例如只有一行），返回 -1。
        """
        if len(lines) <= 1:
            return -1

        # 优先查找段落分隔符 "\n\n"
        # 这对应于一个空行
        for i in range(len(lines) - 2, 0, -1): # 从倒数第二行向前找到第二行
            if not lines[i].strip() and lines[i+1].strip(): # 当前行是空行，下一行不是
                 # 检查前一行也不是空行，确保是段落间的分隔
                 if i > 0 and lines[i-1].strip():
                     return i + 1 # 在空行之后分割

        # 如果没有找到段落分隔符，则在最后一个换行符处分割
        # （即在倒数第二行之后分割）
        if len(lines) > 1:
             return len(lines) - 1 # 在倒数第二行之后分割（即保留最后一行给下一个块）

        return -1 # 理论上如果行数>1总会找到换行符，但作为保险

    def _split_chunk_by_size(self, chunk: Chunk) -> List[Chunk]:
        """将超出 chunk_size 的块分割成更小的块，优先使用分隔符。"""
        if self._chunk_size is None: # 如果未设置 chunk_size，则不分割
             return [chunk]

        sub_chunks = []
        current_lines = []
        current_non_code_len = 0
        in_code = False
        code_fence = None
        lines = chunk.content.split('\n')

        for line_idx, line in enumerate(lines):
            stripped_line = line.strip()
            is_entering_code = False
            is_exiting_code = False

            # --- 代码块边界检查 ---
            if not in_code:
                if stripped_line.startswith("```") and stripped_line.count("```") == 1:
                    is_entering_code = True; code_fence = "```"
                elif stripped_line.startswith("~~~") and stripped_line.count("~~~") == 1:
                    is_entering_code = True; code_fence = "~~~"
            elif in_code and code_fence is not None and stripped_line.startswith(code_fence):
                is_exiting_code = True
            # --- 代码块边界检查结束 ---

            # --- 计算行长度贡献 ---
            line_len_contribution = 0
            if not in_code and not is_entering_code:
                line_len_contribution = self._length_function(line) + 1# +1 for newline
            elif is_exiting_code:
                line_len_contribution = self._length_function(line) + 1
            # --- 计算行长度贡献结束 ---

            # --- 检查是否需要分割 ---
            split_needed = (
                line_len_contribution > 0 and
                current_non_code_len + line_len_contribution > self._chunk_size and
                current_lines # 必须已有内容才能分割
            )

            if split_needed:
                # 尝试找到最佳分割点
                split_line_idx = self._find_best_split_point(current_lines)

                if split_line_idx != -1 and split_line_idx > 0: # 确保不是在第一行就分割
                    lines_to_chunk = current_lines[:split_line_idx]
                    remaining_lines = current_lines[split_line_idx:]

                    # 创建并添加上一个子块
                    content = "\n".join(lines_to_chunk)
                    sub_chunks.append(Chunk(content=content, metadata=chunk.metadata.copy()))

                    # 开始新的子块，包含剩余行和当前行
                    current_lines = remaining_lines + [line]
                    # 重新计算新 current_lines 的非代码长度
                    current_non_code_len = self._calculate_length_excluding_code("\n".join(current_lines))

                else: # 找不到好的分割点或 current_lines 太短，执行硬分割
                    content = "\n".join(current_lines)
                    sub_chunks.append(Chunk(content=content, metadata=chunk.metadata.copy()))
                    current_lines = [line]
                    current_non_code_len = line_len_contribution if not is_entering_code else 0

            else: # 不需要分割，将行添加到当前子块
                current_lines.append(line)
                if line_len_contribution > 0:
                    current_non_code_len += line_len_contribution
            # --- 检查是否需要分割结束 ---


            # --- 更新代码块状态 ---
            if is_entering_code: in_code = True
            elif is_exiting_code: in_code = False; code_fence = None
            # --- 更新代码块状态结束 ---

        # 添加最后一个子块
        if current_lines:
            content = "\n".join(current_lines)
            # 最后检查一次这个块是否超长（可能只有一个元素但超长）
            final_non_code_len = self._calculate_length_excluding_code(content)
            if final_non_code_len > self._chunk_size and len(sub_chunks) > 0:
                 # 如果最后一个块超长，并且不是唯一的块，可能需要警告或特殊处理
                 # 这里简单地添加它，即使它超长
                 pass# logger.warning(f"Final chunk exceeds chunk_size: {final_non_code_len} > {self._chunk_size}")
            sub_chunks.append(Chunk(content=content, metadata=chunk.metadata.copy()))

        return sub_chunks if sub_chunks else [chunk]


    def _aggregate_lines_to_chunks(self, lines: List[LineType],
                                   base_meta: dict) -> List[Chunk]:
        """将具有共同元数据的行合并成块。"""
        aggregated_chunks: List[LineType] = []

        for line in lines:
            if aggregated_chunks and aggregated_chunks[-1]["metadata"] == line["metadata"]:
                # 追加内容，保留换行符
                aggregated_chunks[-1]["content"] += "\n" + line["content"]
            else:
                # 创建新的聚合块，使用 copy 防止后续修改影响
                aggregated_chunks.append(copy.deepcopy(line))

        final_chunks = []
        for chunk_data in aggregated_chunks:
            final_metadata = base_meta.copy()
            final_metadata.update(chunk_data['metadata'])
            # 在这里移除 strip()，因为后续的 _split_chunk_by_size 需要原始换行符
            final_chunks.append(
                Chunk(content=chunk_data["content"], # 移除 .strip()
                      metadata=final_metadata)
            )
        return final_chunks
      
    @task(name="split_text")
    def split_text(self, text: str, metadata: Optional[dict] = None) -> List[Chunk]:
        """基于标题分割 Markdown 文本，并根据 chunk_size 进一步细分。"""
        logger = get_run_logger()
        base_metadata = metadata or {}
        lines = text.split("\n")
        lines_with_metadata: List[LineType] = []
        current_content: List[str] = []
        current_metadata: Dict[str, str] = {}
        header_stack: List[HeaderType] = []

        logger.info(f"开始处理Markdown分割，初始元数据: {base_metadata}，总行数: {len(lines)}")
        in_code_block = False
        opening_fence = ""

        for line_num, line in enumerate(lines):
            stripped_line = line.strip()

            # --- 代码块处理逻辑开始 ---
            is_code_fence = False
            if not in_code_block:
                if stripped_line.startswith("```") and stripped_line.count("```") == 1:
                    in_code_block = True
                    opening_fence = "```"
                    is_code_fence = True
                    logger.info(f"检测到代码块开始于第{line_num+1}行，类型: ```")
                elif stripped_line.startswith("~~~") and stripped_line.count("~~~") == 1:
                    in_code_block = True
                    opening_fence = "~~~"
                    is_code_fence = True
                    logger.info(f"检测到代码块开始于第{line_num+1}行，类型: ~~~")
            elif in_code_block and opening_fence and stripped_line.startswith(opening_fence):
                logger.info(f"检测到代码块结束于第{line_num+1}行")
                in_code_block = False
                opening_fence = ""
                is_code_fence = True
            # --- 代码块处理逻辑结束 ---

            if in_code_block or is_code_fence:
                current_content.append(line)
                continue

            # --- 标题处理逻辑开始 ---
            found_header = False
            for sep, name in self.headers_to_split_on:
                if stripped_line.startswith(sep) and (len(stripped_line) == len(sep) or stripped_line[len(sep)] == " "):
                    found_header = True
                    header_level = sep.count("#")
                    header_data = stripped_line[len(sep):].strip()
                    logger.info(f"第{line_num+1}行检测到{name}标题: '{header_data}' (等级{header_level})")

                    if current_content:
                        logger.info(f"聚合段落完成，行数: {len(current_content)}，当前元数据: {current_metadata}")
                        lines_with_metadata.append({
                            "content": "\n".join(current_content),
                            "metadata": current_metadata.copy(),
                        })
                        current_content = []

                    while header_stack and header_stack[-1]["level"] >= header_level:
                        popped = header_stack.pop()
                        logger.debug(f"弹出标题栈: {popped['name']} (等级{popped['level']})")
                    new_header = {"level": header_level, "name": name, "data": header_data}
                    header_stack.append(new_header)
                    logger.info(f"更新标题栈 => {[h['name']+f'(L{h['level']})' for h in header_stack]}")
                    current_metadata = {h["name"]: h["data"] for h in header_stack}
                    
                    if not self.strip_headers:
                        current_content.append(line)
                    break
            # --- 标题处理逻辑结束 ---

            if not found_header:
                if line.strip() or current_content:
                    current_content.append(line)

        if current_content:
            logger.info(f"最终段落聚合完成，行数: {len(current_content)}，元数据: {current_metadata}")
            lines_with_metadata.append({
                "content": "\n".join(current_content),
                "metadata": current_metadata.copy(),
            })

        logger.info(f"初步聚合完成，总段落数: {len(lines_with_metadata)}")
        aggregated_chunks = self._aggregate_lines_to_chunks(lines_with_metadata, base_meta=base_metadata)
        logger.info(f"标题聚合完成，总块数: {len(aggregated_chunks)}")
        for idx, chunk in enumerate(aggregated_chunks):
            logger.info(f"聚合块#{idx+1} 长度: {len(chunk.content)}字符 | 元数据: {chunk.metadata}")

        if self._chunk_size is None:
            return aggregated_chunks
        else:
            final_chunks = []
            for chunk in aggregated_chunks:
                non_code_len = self._calculate_length_excluding_code(chunk.content)
                logger.debug(f"块检查: 非代码长度={non_code_len}/阀值={self._chunk_size}")
                
                if non_code_len > self._chunk_size:
                    logger.warning(f"需要进行二次分割 (长度{non_code_len} > {self._chunk_size})")
                    split_sub_chunks = self._split_chunk_by_size(chunk)
                    logger.info(f"分割完成，得到{len(split_sub_chunks)}个子块")
                    final_chunks.extend(split_sub_chunks)
                else:
                    logger.debug("块大小符合要求，无需分割")
                    final_chunks.append(chunk)
            
            total_chars = sum(len(c.content) for c in final_chunks)
            logger.info(f"最终分割完成，总块数: {len(final_chunks)}，总字符数: {total_chars}")
            return final_chunks


# --- 主要执行 / 测试块 ---
if __name__ == '__main__':
    # 测试代码块
    try:
        # 假设  RevolutionMaximaUserManualCN_content_list_output.md 文件存在于脚本同目录下
        with open("RevolutionMaximaUserManualCN_content_list_output.md", "r", encoding="utf-8") as f:
            text = f.read()

        # 策略 1: 仅基于标题分割 (不设置 chunk_size)
        # 效果: 生成的块数量较少，每个块对应一个最低级别的标题段落。
        #       块的大小可能非常不均匀，有些块可能非常大。
        #       代码块始终包含在它们所属的标题段落内。
        # print("--- Splitting without chunk_size limit (Header-based only) ---")
        # splitter_no_limit = MarkdownHeaderTextSplitter()
        # chunks_no_limit = splitter_no_limit.split_text(text)
        # print(f"Total chunks: {len(chunks_no_limit)}")
        # 取消注释以查看详细输出
        # for chunk in chunks_no_limit:
        #     print(chunk.to_markdown(return_all=True))
        #     print("=" * 40)

        # print("\n" + "===" * 20 + "\n")

        # 策略 2: 基于标题分割，然后根据 chunk_size 和分隔符进一步细分
        # 效果: 首先按标题分割，然后对于超出 chunk_size 的块，
        #       会尝试在更自然的边界（如段落 `\n\n` 或句子/行 `\n`，以及其他标点）进行分割。
        #       目标是使块的非代码内容长度接近但不超过 chunk_size。
        #       代码块保持完整，并且其内容不计入 chunk_size 计算。
        #       这通常能产生大小更均匀、更适合后续处理（如 RAG）的块。
        print("--- Splitting with chunk_size = 800 (Header-based + Size/Separator-based refinement) ---")
        # 使用默认分隔符: ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; ", "，", ", "]
        # 并启用 is_separator_regex=True 以处理中文标点等
        splitter_with_limit = MarkdownHeaderTextSplitter(chunk_size=800, is_separator_regex=True) # 注意添加 is_separator_regex=True 以使用默认中文分隔符
        chunks_with_limit = splitter_with_limit.split_text(text)
        print(f"Total chunks: {len(chunks_with_limit)}")
        for i, chunk in enumerate(chunks_with_limit):
            print(f"--- Chunk {i+1} ---")
            non_code_len = splitter_with_limit._calculate_length_excluding_code(chunk.content)
            print(f"Content Length (Total): {len(chunk.content)}")
            print(f"Content Length (Non-Code): {non_code_len}") # 检查非代码长度是否接近 chunk_size
            print(f"Metadata: {chunk.metadata}")
            # print("\n--- Markdown (Content Only) ---")
            # print(chunk.to_markdown())
            print("\n--- Markdown (With Metadata) ---")
            print(chunk.to_markdown(return_all=True))
            print("====" * 20) # 缩短分隔符以便查看更多块

    except FileNotFoundError:
        print("Error:  RevolutionMaximaUserManualCN_content_list_output.md not found. Please create the file for testing.")