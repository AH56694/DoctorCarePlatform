"""意图识别模块"""  # 模块文档字符串，说明本模块的功能

from .classifier import IntentClassifier, IntentType, IntentResult  # 从当前包（. 表示当前目录）的 classifier 模块导入：IntentClassifier（意图分类器类）、IntentType（意图类型枚举）、IntentResult（意图识别结果数据类）

__all__ = ["IntentClassifier", "IntentType", "IntentResult"]  # __all__ 列表定义了 from intent import * 时导出的公开符号，限制导出范围
