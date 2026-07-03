from abc import ABC, abstractmethod  # 导入抽象基类和抽象方法装饰器（类似 Java 的 abstract 类/interface）
from typing import Dict, Any, Optional  # 导入类型注解：Dict=字典类型，Any=任意类型，Optional=可选类型（类似 Java 的 Map<?,?>, Object, @Nullable）
from dataclasses import dataclass, field  # 导入数据类装饰器和字段工厂（@dataclass 类似 Java 的 Lombok @Data，自动生成 __init__/__repr__ 等）


@dataclass  # 数据类装饰器，自动生成 __init__、__repr__、__eq__ 等方法（类似 Java 的 Lombok @Data）
class ToolMetadata:  # 定义工具元数据类，用于存储工具的配置信息
    """工具元数据"""
    timeout_ms: int = 30000  # 超时时间（毫秒），默认30秒（类似 Java 的 int 类型字段带默认值）
    max_retries: int = 3     # 最大重试次数，默认3次
    permission: str = "user"  # 权限级别，"user" 或 "admin"
    description: str = ""  # 工具描述，默认空字符串


@dataclass  # 数据类装饰器
class SchemaProperty:  # 定义 Schema 属性类，描述工具参数的属性（类似 Java 的参数描述 DTO）
    """Schema 属性"""
    type: str  # 参数类型：string, number, boolean, object, array（注意：这是字符串，不是 Python 类型）
    description: str  # 参数描述
    required: bool = True  # 是否必填，默认 True（类似 Java 的 @NotNull）
    default: Any = None  # 默认值，Any 表示可以是任意类型（类似 Java 的 Object）


@dataclass  # 数据类装饰器
class ToolSchema:  # 定义工具输入/输出的 Schema 结构（类似 Java 的 JSON Schema DTO）
    """工具输入/输出 schema"""
    properties: Dict[str, SchemaProperty]  # 属性字典，key 是参数名，value 是 SchemaProperty（类似 Java 的 Map<String, SchemaProperty>）
    type: str = "object"  # Schema 类型，默认 "object"
    required: list = field(default_factory=list)  # 必填字段列表，field(default_factory=list) 类似 Java 的 new ArrayList<>()，避免可变默认参数陷阱


class Tool(ABC):  # 定义抽象基类 Tool，继承自 ABC（类似 Java 的 abstract class Tool）
    """工具基类"""

    def __init__(self, name: str, description: str, input_schema: ToolSchema,  # 构造函数（类似 Java 的构造器）
                 output_schema: ToolSchema, metadata: Optional[ToolMetadata] = None):  # metadata 参数可选（类似 Java 的 @Nullable）
        self.name = name  # 工具名称，self 相当于 Java 的 this
        self.description = description  # 工具描述
        self.input_schema = input_schema  # 输入 Schema
        self.output_schema = output_schema  # 输出 Schema
        self.metadata = metadata or ToolMetadata()  # 元数据，如果未提供则使用默认值（类似 Java 的 Objects.requireNonNullElse(metadata, new ToolMetadata())）

    @abstractmethod  # 标记为抽象方法（类似 Java 的 abstract 方法），子类必须实现，否则实例化时会报错
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 执行方法，接收字典参数，返回字典结果
        """执行工具逻辑"""
        pass  # 占位符，子类必须重写（类似 Java 的 abstract 方法没有方法体）

    def validate_input(self, parameters: Dict[str, Any]) -> bool:  # 验证输入参数的方法，返回 bool（类似 Java 的 boolean）
        """验证输入参数"""
        for name, property in self.input_schema.properties.items():  # 遍历 Schema 中的所有属性（items() 类似 Java 的 Map.entrySet()）
            if property.required and name not in parameters:  # 如果属性是必填的但参数中没有提供
                return False  # 验证失败
            if name in parameters:  # 如果参数中包含该属性
                # 简单类型检查
                if property.type == "number" and not isinstance(parameters[name], (int, float)):  # isinstance 类似 Java 的 instanceof
                    return False  # 数字类型检查
                if property.type == "string" and not isinstance(parameters[name], str):  # 字符串类型检查
                    return False
                if property.type == "boolean" and not isinstance(parameters[name], bool):  # 布尔类型检查
                    return False
        return True  # 所有检查通过
