from typing import Dict, Any  # 导入类型注解：Dict=字典类型，Any=任意类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.llm import LLMService  # 导入 LLM（大语言模型）服务类
from core.config import config  # 导入全局配置单例


class OCRExtractTool(Tool):  # OCR 文字提取工具，继承自 Tool 抽象基类
    """OCR文字提取工具"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "image_url": SchemaProperty(  # 图片 URL 参数
                    type="string",  # 字符串类型
                    description="图片URL",  # 参数描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "extracted_text": SchemaProperty(  # 提取的文字输出
                    type="string",  # 字符串类型
                    description="提取的文字",  # 描述
                    required=True  # 必填
                ),
                "image_url": SchemaProperty(  # 图片 URL 输出（回传）
                    type="string",  # 字符串类型
                    description="图片URL",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=30000,  # 超时时间30秒（OCR 处理可能较慢）
            max_retries=2,  # 最大重试2次
            permission="user",  # 用户级权限
            description="从图片中提取文字"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="ocr_extract",  # 工具名称
            description="从图片中提取文字",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        # 初始化 LLM 服务（用于 OCR 功能）
        self.llm_service = LLMService()  # 创建 LLM 服务实例，利用多模态模型的图像识别能力实现 OCR

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行 OCR 文字提取
        """执行OCR文字提取"""
        image_url = parameters.get("image_url")  # 获取图片 URL

        config.logger.info(f"Extracting text from image: {image_url}")  # 记录提取日志

        try:  # 尝试提取文字
            # 使用 LLM 服务的 OCR 功能
            extracted_text = self.llm_service.extract_text_from_image(image_url)  # 调用 LLM 服务的图像文字提取方法

            config.logger.info(f"OCR extraction completed, extracted {len(extracted_text)} characters")  # 记录完成日志

            return {  # 返回结果字典
                "extracted_text": extracted_text,  # 提取的文字内容
                "image_url": image_url  # 原始图片 URL
            }

        except Exception as e:  # 捕获提取异常
            config.logger.error(f"OCR extraction failed: {e}")  # 记录错误日志
            return {  # 返回错误信息
                "extracted_text": f"无法从图片中提取文字: {str(e)}",  # 错误信息作为提取结果
                "image_url": image_url  # 原始图片 URL
            }
