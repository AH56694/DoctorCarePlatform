from typing import Dict, Any  # 导入类型注解：Dict=字典类型，Any=任意类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.llm import LLMService  # 导入 LLM（大语言模型）服务类
from core.config import config  # 导入全局配置单例


class QuestionRewriteTool(Tool):  # 问题重写工具，继承自 Tool 抽象基类
    """问题重写工具"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "question": SchemaProperty(  # 原始问题参数
                    type="string",  # 字符串类型
                    description="原始问题",  # 参数描述
                    required=True  # 必填
                ),
                "conversation_context": SchemaProperty(  # 对话上下文参数
                    type="string",  # 字符串类型
                    description="对话上下文（可选）",  # 参数描述
                    required=False,  # 非必填
                    default=""  # 默认空字符串
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "rewritten_question": SchemaProperty(  # 重写后的问题输出
                    type="string",  # 字符串类型
                    description="重写后的问题",  # 描述
                    required=True  # 必填
                ),
                "original_question": SchemaProperty(  # 原始问题输出
                    type="string",  # 字符串类型
                    description="原始问题",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=15000,  # 超时时间15秒
            max_retries=2,  # 最大重试2次
            permission="user",  # 用户级权限
            description="重写用户问题以提高检索效果"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="question_rewrite",  # 工具名称
            description="重写用户问题以提高检索效果",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        # 初始化 LLM 服务
        self.llm_service = LLMService()  # 创建 LLM 服务实例，用于调用大模型重写问题

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行问题重写
        """执行问题重写"""
        question = parameters.get("question")  # 获取原始问题
        conversation_context = parameters.get("conversation_context", "")  # 获取对话上下文，默认空字符串

        # 构建重写提示
        rewrite_prompt = f"""  # 使用 f-string 构建多行提示词模板
        你是一个问题重写专家。请将用户的原始问题重写为更适合知识库检索的形式。

        原始问题：{question}

        对话上下文：
        {conversation_context if conversation_context else "无"}  # 三元表达式（类似 Java 的 condition ? a : b），如果有上下文则使用，否则显示"无"

        要求：
        0. 只对用户的输入进行改写， 不需要对用户的问题进行解释
        1. 保持问题的核心意图不变
        2. 使用更正式、明确的语言
        3. 补充可能缺失的关键信息
        4. 优化关键词，使其更适合向量检索
        5. 直接返回重写后的问题，不要添加任何前缀或解释
        """

        # 使用 LLM 重写问题
        try:  # 尝试调用 LLM（类似 Java 的 try-catch）
            # 使用 LLM 服务生成重写后的问题
            # 这里使用 get_answer 方法，因为我们需要的是 LLM 的生成能力
            rewritten_question = self.llm_service.get_answer(  # 调用 LLM 服务的 get_answer 方法
                question=rewrite_prompt,  # 传入重写提示词作为问题
                context_docs=[],  # 不需要上下文文档（空列表）
                conversation_context=""  # 不需要额外的对话上下文
            )

            # 清理结果
            rewritten_question = rewritten_question.strip()  # strip() 去除首尾空白字符（类似 Java 的 String.trim()）

            config.logger.info(f"Question rewritten: '{question}' -> '{rewritten_question}'")  # 记录重写结果日志

            return {  # 返回结果字典
                "rewritten_question": rewritten_question,  # 重写后的问题
                "original_question": question  # 原始问题
            }

        except Exception as e:  # 捕获所有异常
            config.logger.error(f"Question rewrite failed: {e}")  # 记录错误日志
            # 如果重写失败，返回原始问题
            return {  # 降级返回原始问题
                "rewritten_question": question,  # 重写失败时直接返回原始问题
                "original_question": question  # 原始问题
            }
