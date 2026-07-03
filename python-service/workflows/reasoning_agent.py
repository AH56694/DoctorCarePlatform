from typing import Dict, Any, Optional, List  # 导入类型提示：Dict 字典类型，Any 任意类型，Optional 可为 None，List 列表类型
from core.llm import LLMService  # 导入 LLM 服务类
from core.vector_store import vector_store  # 导入全局向量存储实例
from tools.registry import tool_registry  # 导入工具注册表实例
import logging  # 导入日志模块
import json  # 导入 JSON 模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class ReasoningAgent:  # 定义推理 Agent 类（处理复杂问题的分步推理）
    """Reasoning Agent - 处理复杂问题的分步推理（Chain-of-Thought）"""

    def __init__(self):  # 构造函数
        self.llm_service = LLMService()  # 初始化 LLM 服务实例
        self.vector_store = vector_store  # 引用全局向量存储实例

    def reason(self, question: str, context: str = "",  # reason 方法：执行推理流程
               conversation_id: str = None) -> Dict[str, Any]:  # conversation_id 类型提示为 str（未用 Optional，但默认 None 也可）
        """执行推理流程：分解 → 逐个检索+推理 → 汇总"""
        logger.info(f"[ReasoningAgent] Starting reasoning for: {question[:50]}...")

        try:
            # Step 1：问题分解
            sub_questions = self._decompose_question(question)  # 将复杂问题分解为子问题列表
            logger.info(f"[ReasoningAgent] Decomposed into {len(sub_questions)} sub-questions")  # len() 获取列表长度

            # Step 2：逐个子问题检索 + 推理
            reasoning_steps = []  # 初始化推理步骤列表
            for sub_q in sub_questions:  # 遍历每个子问题
                docs = self.vector_store.search(sub_q, k=3, similarity_threshold=0.3)  # 为每个子问题检索相关文档（k=3 返回3个结果），推理场景适当放宽阈值到0.3
                sub_answer = self._reason_sub_question(sub_q, docs, context)  # 对子问题进行推理得到子答案
                reasoning_steps.append({  # 添加推理步骤记录
                    "sub_question": sub_q,  # 子问题
                    "sources": [  # 来源列表（列表推导式，类似 Java 的 stream().map().collect()）
                        {"doc_id": getattr(doc, 'metadata', {}).get("doc_id"),  # getattr() 安全获取 metadata 属性
                         "doc": getattr(doc, 'metadata', {}).get("source", "未知文档")}  # 获取文档来源
                        for doc in docs  # 遍历每个文档
                    ],
                    "reasoning": sub_answer  # 子问题的推理结果
                })

            # Step 3：汇总生成最终答案
            final_answer = self._synthesize_answer(question, reasoning_steps)  # 汇总所有子答案生成最终答案

            # 合并所有来源
            all_sources = []  # 初始化全部来源列表
            seen_ids = set()  # 已见文档ID集合（用于去重）
            for step in reasoning_steps:  # 遍历每个推理步骤
                for src in step["sources"]:  # 遍历步骤中的来源
                    doc_id = src.get("doc_id")  # 获取文档ID
                    if doc_id and doc_id not in seen_ids:  # 如果有文档ID且未见过
                        seen_ids.add(doc_id)  # 添加到已见集合
                        all_sources.append(src)  # 添加到全部来源列表

            # 写入会话记忆
            if conversation_id and tool_registry.has_tool("conversation_memory_write"):  # 如果有会话ID且存在写入工具
                try:
                    tool_registry.invoke_tool(  # 保存用户问题
                        "conversation_memory_write",
                        {"conversation_id": conversation_id, "role": "user", "content": question}
                    )
                    tool_registry.invoke_tool(  # 保存 AI 回复
                        "conversation_memory_write",
                        {"conversation_id": conversation_id, "role": "assistant", "content": final_answer}
                    )
                except Exception as e:
                    logger.warning(f"[ReasoningAgent] Failed to write memory: {e}")

            return {  # 返回推理结果
                "answer": final_answer,  # 最终答案
                "reasoning_steps": reasoning_steps,  # 推理步骤列表
                "sources": all_sources,  # 去重后的引用来源
                "has_sources": len(all_sources) > 0,  # 是否有引用来源
                "task_type": "reasoning"  # 任务类型
            }

        except Exception as e:
            logger.error(f"[ReasoningAgent] Reasoning failed: {e}", exc_info=True)  # exc_info=True 记录完整堆栈
            return {  # 返回错误响应
                "answer": "抱歉，处理您的复杂问题时遇到了错误，请稍后再试。",
                "reasoning_steps": [],  # 空的推理步骤
                "sources": [],  # 空的来源列表
                "has_sources": False,
                "task_type": "reasoning",
                "error": True  # 错误标志
            }

    def _decompose_question(self, question: str) -> List[str]:  # 分解复杂问题为子问题列表
        """将复杂问题分解为子问题"""
        if not self.llm_service.llm:  # 如果 LLM 不可用
            return [question]  # 返回只包含原始问题的列表（无法分解）

        from langchain_core.prompts import PromptTemplate  # 导入 LangChain 提示模板类
        from langchain_core.output_parsers import StrOutputParser  # 导入字符串输出解析器

        prompt = PromptTemplate.from_template(  # 从模板字符串创建提示模板（类似 Java 的模板引擎）
            """请将以下复杂问题分解为 2-4 个简单的子问题，便于逐个检索和推理。

问题：{question}

请以 JSON 数组格式输出子问题列表，例如：["子问题1", "子问题2"]
只输出 JSON 数组，不要其他内容。"""
        )

        try:
            chain = prompt | self.llm_service.llm | StrOutputParser()  # LangChain 管道操作符 |（类似 Unix 管道）：prompt -> LLM -> 解析器
            response = chain.invoke({"question": question}).strip()  # invoke() 执行链路，传入参数字典；.strip() 去除首尾空白

            # 处理可能的 markdown 代码块
            if response.startswith("```"):  # .startswith() 检查字符串是否以指定前缀开头（类似 Java 的 startsWith()）
                response = response.split("\n", 1)[1] if "\n" in response else response[3:]  # .split("\n", 1) 最多分割1次，[1] 取第二部分
                response = response.rsplit("```", 1)[0]  # .rsplit("```", 1) 从右侧分割1次，[0] 取第一部分（去除结尾的 ```）

            sub_questions = json.loads(response.strip())  # 解析 JSON 字符串为 Python 对象（类似 Java 的 ObjectMapper.readValue()）
            if isinstance(sub_questions, list) and len(sub_questions) > 0:  # isinstance() 检查类型是否为列表，且列表不为空
                return sub_questions[:4]  # 最多返回4个子问题（切片截取）
        except Exception as e:
            logger.warning(f"[ReasoningAgent] Failed to decompose question: {e}")

        return [question]  # 分解失败时返回原始问题

    def _reason_sub_question(self, question: str, docs: list, context: str) -> str:  # 对单个子问题进行推理
        """对单个子问题进行推理"""
        if not self.llm_service.llm:  # 如果 LLM 不可用
            return "无法推理（LLM 不可用）"

        doc_text = "\n".join([  # 将文档列表合并为文本（列表推导式 + join）
            getattr(doc, 'page_content', str(doc)) if hasattr(doc, 'page_content')  # hasattr() 检查对象是否有 page_content 属性
            else doc.get('content', str(doc)) if isinstance(doc, dict) else str(doc)  # 多层三元表达式：字典取 content，其他转字符串
            for doc in docs  # 遍历每个文档
        ]) if docs else "（无相关文档）"  # 如果文档列表为空则使用占位文本

        from langchain_core.prompts import PromptTemplate  # 导入提示模板
        from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器

        prompt = PromptTemplate.from_template(  # 创建子问题推理提示模板
            """基于以下参考资料，回答子问题。

参考资料：
{doc_text}

对话上下文：{context}

子问题：{question}

请给出简洁准确的回答。"""
        )

        chain = prompt | self.llm_service.llm | StrOutputParser()  # 构建 LangChain 管道
        return chain.invoke({  # 执行推理并返回结果
            "doc_text": doc_text,  # 参考文档文本
            "context": context or "无",  # or 运算符：context 为空字符串时使用"无"
            "question": question  # 子问题
        }).strip()  # 去除首尾空白

    def _synthesize_answer(self, original_question: str, reasoning_steps: list) -> str:  # 汇总推理结果
        """汇总推理结果，生成最终答案"""
        if not self.llm_service.llm:  # 如果 LLM 不可用
            return "\n\n".join([step["reasoning"] for step in reasoning_steps])  # 用双换行符拼接所有子答案

        steps_text = "\n".join([  # 将推理步骤格式化为文本
            f"Q: {step['sub_question']}\nA: {step['reasoning']}"  # 每个 step 包含问题和答案
            for step in reasoning_steps  # 遍历推理步骤
        ])

        from langchain_core.prompts import PromptTemplate  # 导入提示模板
        from langchain_core.output_parsers import StrOutputParser  # 导入输出解析器

        prompt = PromptTemplate.from_template(  # 创建汇总提示模板
            """基于以下分步推理结果，回答用户的原始问题。

分步推理：
{steps_text}

原始问题：{original_question}

请给出完整、准确、结构化的回答。"""
        )

        chain = prompt | self.llm_service.llm | StrOutputParser()  # 构建 LangChain 管道
        return chain.invoke({  # 执行汇总推理
            "steps_text": steps_text,  # 推理步骤文本
            "original_question": original_question  # 原始问题
        }).strip()  # 去除首尾空白并返回