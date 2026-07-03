from typing import Dict, Any  # 导入类型注解：Dict=字典类型，Any=任意类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.llm import LLMService  # 导入 LLM（大语言模型）服务类
from core.config import config  # 导入全局配置单例


class DocSummaryTool(Tool):  # 文档摘要工具，继承自 Tool 抽象基类
    """文档摘要工具"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "content": SchemaProperty(  # 文档内容参数
                    type="string",  # 字符串类型
                    description="文档内容",  # 参数描述
                    required=True  # 必填
                ),
                "max_length": SchemaProperty(  # 摘要最大长度参数
                    type="number",  # 数字类型
                    description="摘要最大长度",  # 参数描述
                    required=False,  # 非必填
                    default=200  # 默认200字
                ),
                "focus": SchemaProperty(  # 摘要重点参数
                    type="string",  # 字符串类型
                    description="摘要重点（可选）",  # 参数描述
                    required=False  # 非必填
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "summary": SchemaProperty(  # 摘要输出
                    type="string",  # 字符串类型
                    description="文档摘要",  # 描述
                    required=True  # 必填
                ),
                "original_length": SchemaProperty(  # 原始文档长度输出
                    type="number",  # 数字类型
                    description="原始文档长度",  # 描述
                    required=True  # 必填
                ),
                "summary_length": SchemaProperty(  # 摘要长度输出
                    type="number",  # 数字类型
                    description="摘要长度",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=20000,  # 超时时间20秒
            max_retries=2,  # 最大重试2次
            permission="user",  # 用户级权限
            description="生成文档摘要"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="doc_summary",  # 工具名称
            description="生成文档摘要",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        # 初始化 LLM 服务
        self.llm_service = LLMService()  # 创建 LLM 服务实例，用于调用大模型生成摘要

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行文档摘要生成
        """执行文档摘要生成"""
        content = parameters.get("content")  # 获取文档内容
        max_length = int(parameters.get("max_length", 200))  # 获取摘要最大长度，默认200
        focus = parameters.get("focus", "")  # 获取摘要重点，默认空字符串

        original_length = len(content)  # 计算原始文档长度（len 类似 Java 的 String.length()）

        config.logger.info(f"Generating summary for document of length {original_length}, max summary length: {max_length}")  # 记录日志

        # 构建摘要提示
        summary_prompt = f"""  # 使用 f-string 构建多行提示词模板
        请为以下文档生成一个简洁的摘要：

        {content}

        要求：
        1. 摘要长度不超过 {max_length} 字
        2. 包含文档的核心内容和主要观点
        3. 语言简洁明了
        4. {'重点关注：' + focus if focus else ''}  # 三元表达式：如果有重点则拼接，否则空字符串
        5. 直接返回摘要，不要添加任何前缀或解释
        """

        try:  # 尝试调用 LLM 生成摘要
            # 使用 LLM 生成摘要
            summary = self.llm_service.get_answer(  # 调用 LLM 服务的 get_answer 方法
                question=summary_prompt,  # 传入摘要提示词作为问题
                context_docs=[],  # 不需要上下文文档
                conversation_context=""  # 不需要对话上下文
            )

            # 清理摘要
            summary = summary.strip()  # 去除首尾空白字符（类似 Java 的 String.trim()）

            # 确保摘要长度不超过限制
            if len(summary) > max_length:  # 如果摘要超过最大长度
                summary = summary[:max_length] + "..."  # 截断并添加省略号（[:n] 切片类似 Java 的 substring(0, n)）

            summary_length = len(summary)  # 计算摘要实际长度
            config.logger.info(f"Summary generated: {summary_length} characters")  # 记录生成日志

            return {  # 返回结果字典
                "summary": summary,  # 生成的摘要
                "original_length": original_length,  # 原始文档长度
                "summary_length": summary_length  # 摘要长度
            }

        except Exception as e:  # 捕获异常
            config.logger.error(f"Document summary failed: {e}")  # 记录错误日志
            return {  # 返回失败信息
                "summary": f"生成摘要失败: {str(e)}",  # 错误信息作为摘要返回
                "original_length": original_length,  # 原始文档长度
                "summary_length": 0  # 摘要长度为0表示失败
            }
