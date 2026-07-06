import os  # 导入 os 模块，用于文件系统操作
import shutil  # 导入 shutil 模块，用于高级文件操作（如递归删除目录、移动目录等，类似 Java 的 FileUtils）
from typing import List, Optional, Dict, Any  # 导入类型提示：List 列表，Optional 可空类型，Dict 字典，Any 任意类型
from langchain_community.vectorstores import FAISS  # 导入 FAISS 向量存储（Facebook 的向量相似度搜索库）
from langchain_community.embeddings import DashScopeEmbeddings, HuggingFaceEmbeddings  # 导入两种 Embedding 实现：DashScope 云端和 HuggingFace 本地
from langchain_core.documents import Document  # 导入 LangChain 的 Document 类
from langchain_community.vectorstores.utils import DistanceStrategy  # 导入距离策略枚举，用于指定 FAISS 使用内积（余弦相似度）还是 L2 距离
from core.reranker import create_reranker, BaseReranker  # 导入重排序器工厂函数和基类
from core.config import config  # 导入全局配置实例

# pymilvus 和 Milvus 是可选依赖，仅在使用 Milvus 时需要
try:  # try-except 用于处理可选依赖
    from pymilvus import connections, utility  # 导入 Milvus 连接和工具模块
    from langchain_community.vectorstores import Milvus  # 导入 LangChain 的 Milvus 向量存储封装
    MILVUS_AVAILABLE = True  # 标记 Milvus 可用
except ImportError:  # 如果 pymilvus 未安装
    MILVUS_AVAILABLE = False  # 标记 Milvus 不可用


class VectorStoreManager:  # 定义向量存储管理器类
    def __init__(self, persist_directory=None, use_milvus=None):  # 构造方法，支持可选参数
        """
        初始化向量存储管理器

        Args:
            persist_directory: FAISS持久化目录（仅当use_milvus=False时使用）
            use_milvus: 是否使用Milvus（默认从环境变量读取，默认值为True）
        """
        # 从环境变量读取持久化目录，默认值为./faiss_index
        self.persist_directory = persist_directory or config.VECTOR_STORE_PERSIST_DIR  # or 短路求值：有值则使用，否则用配置中的默认值
        # 从环境变量读取use_milvus配置，如果未设置则默认为True
        if use_milvus is None:  # 如果调用者没有传入 use_milvus 参数
            use_milvus = config.USE_MILVUS  # 从配置中读取
        self.use_milvus = use_milvus  # 保存是否使用 Milvus
        # 从环境变量读取集合名称，默认值为ai_knowledge_collection
        self.collection_name = config.VECTOR_STORE_COLLECTION_NAME  # Milvus 集合名称（类似数据库表名）
        self.vector_store = None  # 向量存储实例，初始为 None

        # 初始化Reranker
        self._init_reranker()  # 调用重排序器初始化方法

        # 根据 EMBEDDING_MODEL 配置选择 Embedding 模型
        embedding_model = config.EMBEDDING_MODEL.lower()  # 获取配置中的模型类型并转小写

        if embedding_model == "local":  # 如果使用本地模型
            # 使用本地中文 Embedding 模型（如 BAAI/bge-small-zh-v1.5）
            local_model_path = config.LOCAL_EMBEDDING_MODEL_PATH  # 获取本地模型磁盘路径
            local_model_name = config.LOCAL_EMBEDDING_MODEL  # 获取本地模型名称（HuggingFace格式）

            if local_model_path and os.path.isdir(local_model_path):  # 如果设置了本地路径且目录存在
                config.logger.info(f"Loading local Embeddings from disk path: {local_model_path}")  # 记录从本地磁盘加载
                self.embeddings = HuggingFaceEmbeddings(model_name=local_model_path)  # 直接从本地目录加载，不联网
            else:  # 没有设置本地路径，使用HuggingFace名称（会自动下载/使用缓存）
                config.logger.info(f"Using HuggingFace Embeddings ({local_model_name}), will download if not cached")  # 记录日志
                self.embeddings = HuggingFaceEmbeddings(model_name=local_model_name)  # 创建 HuggingFace Embedding 实例（首次会下载）
        else:  # 默认使用云端模型
            # 默认使用阿里云 DashScope Embeddings (text-embedding-v1)
            api_key = config.DASHSCOPE_API_KEY  # 获取 API 密钥
            if api_key:  # 如果有密钥
                config.logger.info("Using DashScope Embeddings (text-embedding-v1)")  # 记录日志
                self.embeddings = DashScopeEmbeddings(  # 创建 DashScope Embedding 实例
                    model="text-embedding-v1",  # 使用的 Embedding 模型名称
                    dashscope_api_key=api_key  # API 密钥
                )
            else:  # 没有密钥则回退到本地模型
                config.logger.warning("DASHSCOPE_API_KEY not found. Falling back to local HuggingFace Embeddings.")  # 记录警告
                # 同样优先使用本地磁盘路径
                local_model_path = config.LOCAL_EMBEDDING_MODEL_PATH  # 获取本地模型磁盘路径
                if local_model_path and os.path.isdir(local_model_path):  # 如果设置了本地路径且目录存在
                    self.embeddings = HuggingFaceEmbeddings(model_name=local_model_path)  # 从本地磁盘加载
                else:  # 没有本地路径
                    self.embeddings = HuggingFaceEmbeddings(model_name=config.LOCAL_EMBEDDING_MODEL)  # 使用HuggingFace下载

        # 如果 pymilvus 未安装，强制使用 FAISS
        if self.use_milvus and not MILVUS_AVAILABLE:  # 如果想用 Milvus 但 pymilvus 未安装
            config.logger.warning("pymilvus not installed, falling back to FAISS")  # 记录警告
            self.use_milvus = False  # 强制切换到 FAISS

        # 根据配置选择向量数据库
        if self.use_milvus:  # 如果使用 Milvus
            self._init_milvus()  # 初始化 Milvus
        else:  # 否则使用 FAISS
            self._init_faiss()  # 初始化 FAISS

    def _init_reranker(self):  # 定义初始化重排序器的私有方法
        """初始化Reranker"""  # 方法的 docstring
        reranker_type = config.RERANKER_TYPE  # 从配置获取重排序器类型
        if reranker_type == "none":  # 如果禁用重排序
            self.reranker = None  # 设为 None
            config.logger.info("Reranker is disabled")  # 记录日志
            return  # 提前返回

        try:
            self.reranker = create_reranker(reranker_type)  # 调用工厂函数创建重排序器
            config.logger.info(f"Reranker initialized: {reranker_type}")  # 记录初始化成功
        except Exception as e:  # 捕获异常
            config.logger.error(f"Failed to initialize reranker: {e}")  # 记录错误
            self.reranker = None  # 设为 None 表示未初始化

    def _init_milvus(self):  # 定义初始化 Milvus 连接的私有方法
        """初始化Milvus连接和集合"""  # 方法的 docstring
        try:
            # Milvus连接配置
            milvus_host = config.MILVUS_HOST  # Milvus 主机地址
            milvus_port = config.MILVUS_PORT  # Milvus 端口

            config.logger.info(f"Connecting to Milvus at {milvus_host}:{milvus_port}")  # 记录连接信息
            connections.connect(alias="default", host=milvus_host, port=milvus_port)  # 建立连接，alias 是连接别名

            # 检查连接
            if not connections.has_connection("default"):  # 检查是否连接成功
                raise ConnectionError("Failed to connect to Milvus")  # 抛出连接错误

            config.logger.info("Successfully connected to Milvus")  # 记录连接成功

            # 初始化Milvus向量存储
            self.vector_store = Milvus(  # 创建 Milvus 向量存储实例
                embedding_function=self.embeddings,  # Embedding 函数，用于将文本转为向量
                collection_name=self.collection_name,  # 集合名称
                connection_args={  # 连接参数字典
                    "host": milvus_host,  # 主机
                    "port": milvus_port,  # 端口
                    "alias": "default"  # 连接别名
                },
                # 自动创建集合（如果不存在）
                auto_id=True  # 自动生成文档 ID
            )

            config.logger.info(f"Milvus collection '{self.collection_name}' ready")  # 记录集合就绪

        except Exception as e:  # 捕获异常
            config.logger.error(f"Failed to initialize Milvus: {e}")  # 记录错误
            config.logger.info("Falling back to FAISS...")  # 记录回退
            self.use_milvus = False  # 切换到 FAISS
            self._init_faiss()  # 初始化 FAISS

    def _init_faiss(self):  # 定义初始化 FAISS 的私有方法
        """
        初始化 FAISS 向量存储（作为 Milvus 的 fallback）
        """
        config.logger.info("Using FAISS vector store (fallback mode)")  # 记录使用 FAISS
        if os.path.exists(self.persist_directory):  # 如果持久化目录存在（之前已经创建过索引）
            try:
                self.vector_store = FAISS.load_local(self.persist_directory, self.embeddings, allow_dangerous_deserialization=True)  # 从磁盘加载 FAISS 索引，allow_dangerous_deserialization=True 允许反序列化（有安全风险但必要）
                config.logger.info(f"Loaded existing FAISS index from {self.persist_directory}")  # 记录加载成功
            except Exception as e:  # 加载失败（可能是 Embedding 模型变更导致维度不匹配）
                config.logger.error(f"Error loading existing FAISS index: {e}")  # 记录错误
                config.logger.info("This may be caused by embedding model change (dimension mismatch). Re-initializing empty FAISS vector store...")  # 记录可能原因
                # Backup old index just in case
                if os.path.exists(self.persist_directory + "_backup"):  # 如果备份目录已存在
                    shutil.rmtree(self.persist_directory + "_backup")  # 递归删除备份目录
                shutil.move(self.persist_directory, self.persist_directory + "_backup")  # 将损坏的索引目录移动到备份位置
                self.vector_store = None  # 重置向量存储为 None
        else:  # 持久化目录不存在
            self.vector_store = None  # 设为 None（首次使用时会在 add_documents 中创建）
            config.logger.info("No existing FAISS index found, will create new one when needed")  # 记录提示

    def add_documents(self, documents: List[Document]):  # 定义添加文档到向量库的方法
        """
        添加文档到向量数据库
        """
        if not documents:  # 如果文档列表为空
            return  # 直接返回

        if self.vector_store is None:  # 如果向量库尚未初始化
            if self.use_milvus:  # 使用 Milvus
                # Milvus会自动创建集合
                milvus_host = config.MILVUS_HOST  # 获取 Milvus 主机
                milvus_port = config.MILVUS_PORT  # 获取 Milvus 端口
                self.vector_store = Milvus.from_documents(  # Milvus.from_documents 从文档直接创建集合和索引
                    documents=documents,  # 文档列表
                    embedding=self.embeddings,  # Embedding 函数
                    collection_name=self.collection_name,  # 集合名称
                    connection_args={  # 连接参数
                        "host": milvus_host,
                        "port": milvus_port,
                        "alias": "default"
                    }
                )
                config.logger.info(f"Created Milvus collection '{self.collection_name}' with {len(documents)} documents")  # 记录创建成功
            else:  # 使用 FAISS
                # 使用 MAX_INNER_PRODUCT 策略：归一化向量的内积 = 余弦相似度，分数范围 0~1，越大越相似
                self.vector_store = FAISS.from_documents(
                    documents, self.embeddings,
                    distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT  # 内积（余弦相似度），而非默认的 L2 距离
                )
                self.vector_store.save_local(self.persist_directory)  # 将索引保存到磁盘
                config.logger.info(f"Created FAISS index with {len(documents)} documents")  # 记录创建成功
        else:  # 向量库已存在
            # 添加文档到现有存储
            if self.use_milvus:  # Milvus
                # Milvus添加文档
                self.vector_store.add_documents(documents)  # 向现有集合添加文档
                config.logger.info(f"Added {len(documents)} documents to Milvus")  # 记录添加成功
            else:  # FAISS
                # FAISS添加文档
                self.vector_store.add_documents(documents)  # 向现有索引添加文档
                self.vector_store.save_local(self.persist_directory)  # 保存到磁盘（FAISS 每次添加后需要手动保存）
                config.logger.info(f"Added {len(documents)} documents to FAISS")  # 记录添加成功

    def search(self, query: str, k: int = 3, filter_dict: Optional[Dict[str, Any]] = None, similarity_threshold: float = 0.5, use_rerank: bool = True) -> List[Document]:  # 定义向量搜索方法，支持多种参数
        """
        向量相似度搜索

        Args:
            query: 查询文本
            k: 返回结果数量
            filter_dict: 过滤条件（仅Milvus支持）
            similarity_threshold: 余弦相似度阈值（0.0-1.0），只有分数 >= 此阈值的结果才返回
                                  0.5 = 中等相关, 0.7 = 较相关, 0.9 = 高度相关
            use_rerank: 是否使用Rerank进行结果重排序
        """
        import time  # 局部导入 time 模块
        start_time = time.time()  # 记录开始时间

        if self.vector_store is None:  # 如果向量库未初始化
            config.logger.info(f"Search completed in {time.time() - start_time:.4f}s, no vector store available")  # 记录提示
            return []  # 返回空列表

        try:
            # 初始检索数量应该比最终返回的多，以便Rerank有足够的候选
            initial_k = k * 3 if use_rerank and self.reranker else k  # 如果启用重排序则多取 3 倍候选，否则取 k 个

            search_start = time.time()  # 记录搜索开始时间
            if self.use_milvus and filter_dict:  # Milvus 且有过滤条件
                # Milvus支持过滤查询
                docs_with_scores = self.vector_store.similarity_search_with_score(query, k=initial_k, filter=filter_dict)  # 带过滤条件的相似度搜索
            else:  # FAISS 或无条件查询
                # FAISS或无条件查询
                docs_with_scores = self.vector_store.similarity_search_with_score(query, k=initial_k)  # 相似度搜索，返回 (文档, 分数) 元组列表
            search_time = time.time() - search_start  # 计算搜索耗时
            config.logger.info(f"Vector search completed in {search_time:.4f}s, found {len(docs_with_scores) if isinstance(docs_with_scores, list) else 0} documents")  # 记录搜索结果

            # 提取文档
            if isinstance(docs_with_scores, list):  # isinstance 检查是否为列表类型
                if len(docs_with_scores) > 0 and isinstance(docs_with_scores[0], tuple):  # 检查第一个元素是否为元组
                    # (doc, score) 格式
                    docs = [doc for doc, score in docs_with_scores]  # 列表推导式：提取文档部分，忽略分数
                else:  # 不是元组格式
                    docs = docs_with_scores  # 直接使用
            else:  # 不是列表
                docs = docs_with_scores  # 直接使用

            if use_rerank and self.reranker and isinstance(docs_with_scores, list):
                if len(docs_with_scores) > 0 and isinstance(docs_with_scores[0], tuple):
                    filtered_pairs = [
                        (doc, score)
                        for doc, score in docs_with_scores
                        if score >= similarity_threshold
                    ]
                    if not filtered_pairs:
                        config.logger.info(
                            f"Search completed in {time.time() - start_time:.4f}s, no documents passed threshold before rerank"
                        )
                        return []
                    docs = [doc for doc, _ in filtered_pairs]
                    config.logger.info(
                        f"Filtered rerank candidates by similarity threshold: {len(filtered_pairs)}/{len(docs_with_scores)} kept"
                    )

            # 如果没有启用Rerank或没有Reranker，直接返回初步检索结果
            if not use_rerank or not self.reranker:  # 未启用重排序或没有重排序器
                # FAISS 使用 MAX_INNER_PRODUCT 策略，返回的 score 就是余弦相似度（0~1，越大越相似）
                filtered_docs = []  # 过滤后的文档列表
                for i, (doc, score) in enumerate(docs_with_scores):  # 遍历带相似度分数的文档列表
                    config.logger.info(f"[FAISS] Doc {i}: cosine similarity={score:.4f}, threshold={similarity_threshold}, pass={score >= similarity_threshold}")  # 打印每条结果的余弦相似度
                    if score >= similarity_threshold:  # 余弦相似度越大越相似，分数 >= 阈值 的文档才保留
                        filtered_docs.append(doc)  # 添加到结果
                    else:
                        config.logger.info(f"[FAISS] Filtered out: similarity {score:.4f} < threshold {similarity_threshold}")  # 记录被过滤
                config.logger.info(f"Search completed in {time.time() - start_time:.4f}s, returning {len(filtered_docs)} documents")  # 记录搜索结果
                return filtered_docs  # 返回过滤后的文档

            # 使用Rerank进行重排序
            try:
                rerank_start = time.time()  # 记录重排序开始时间
                rerank_results = self.reranker.rerank(query, docs, top_k=k)  # 调用重排序器，返回前 k 个结果
                rerank_time = time.time() - rerank_start  # 计算重排序耗时
                config.logger.info(f"Rerank completed in {rerank_time:.4f}s, top {len(rerank_results)} results")  # 记录重排序结果

                # 提取重排序后的文档
                reranked_docs = [r.document for r in rerank_results]  # 列表推导式：从结果中提取文档对象

                # Rerank已经按相关性排序，这里不再应用similarity_threshold过滤
                # 但如果需要可以在这里添加额外的过滤逻辑
                config.logger.info(f"Search completed in {time.time() - start_time:.4f}s, returning {len(reranked_docs)} documents")  # 记录最终结果

                return reranked_docs  # 返回重排序后的文档列表

            except Exception as rerank_error:  # 捕获重排序异常
                config.logger.error(f"Rerank failed: {rerank_error}, falling back to vector search")  # 记录错误
                # Rerank失败时，回退到原始的向量搜索结果，同样按余弦相似度过滤
                filtered_docs = []  # 过滤后的文档列表
                for doc, score in docs_with_scores:  # 遍历原始结果
                    if score >= similarity_threshold:  # 余弦相似度越大越相似
                        filtered_docs.append(doc)  # 添加
                config.logger.info(f"Search completed in {time.time() - start_time:.4f}s (Rerank failed, fallback to vector search), returning {len(filtered_docs)} documents")  # 记录回退结果
                return filtered_docs  # 返回过滤后的结果

        except Exception as e:  # 捕获搜索异常
            config.logger.error(f"Search error: {e}")  # 记录错误
            # 如果 similarity_search_with_score 失败，回退到普通搜索
            try:
                fallback_start = time.time()  # 记录回退搜索开始时间
                if self.use_milvus and filter_dict:  # Milvus 且有过滤条件
                    result = self.vector_store.similarity_search(query, k=k, filter=filter_dict)  # 不带分数的搜索
                else:  # FAISS 或无条件
                    result = self.vector_store.similarity_search(query, k=k)  # 简单相似度搜索
                fallback_time = time.time() - fallback_start  # 计算耗时
                config.logger.info(f"Fallback search completed in {fallback_time:.4f}s, returning {len(result)} documents")  # 记录回退结果
                return result  # 返回搜索结果
            except Exception as e2:  # 回退搜索也失败
                config.logger.error(f"Fallback search also failed: {e2}")  # 记录错误
                config.logger.info(f"Search completed in {time.time() - start_time:.4f}s (all searches failed), returning empty results")  # 记录全部失败
                return []  # 返回空列表

    def delete_document(self, doc_id: int):  # 定义删除文档向量的方法
        """
        根据 doc_id 删除文档向量

        Milvus: 支持高效删除
        FAISS: 标记删除（实际需要重建索引）
        """
        if self.vector_store is None:  # 如果向量库未初始化
            config.logger.warning(f"No vector store available, cannot delete doc_id: {doc_id}")  # 记录警告
            return  # 直接返回

        if self.use_milvus:  # 如果使用 Milvus
            # Milvus删除逻辑
            try:
                config.logger.info(f"Deleting document with doc_id: {doc_id} from Milvus")  # 记录删除操作

                # 构建删除表达式（使用类型转换确保安全性）
                if not isinstance(doc_id, int):  # isinstance 检查类型是否为整数
                    raise ValueError(f"doc_id must be an integer, got {type(doc_id)}")  # 抛出类型错误
                delete_expr = f'doc_id in [{doc_id}]'  # 构建删除表达式（类似 SQL 的 WHERE）

                # 执行删除
                result = self.vector_store.delete(expr=delete_expr)  # 执行删除操作
                config.logger.info(f"Milvus delete result: {result}")  # 记录删除结果

                # 可选：压缩集合以释放空间
                # utility.compact(collection_name=self.collection_name)

                config.logger.info(f"Successfully deleted document {doc_id} from Milvus")  # 记录成功

            except Exception as e:  # 捕获异常
                config.logger.error(f"Failed to delete document from Milvus: {e}")  # 记录错误
                # 尝试其他删除方法
                self._delete_document_fallback(doc_id)  # 调用备用删除方法

        else:  # 使用 FAISS
            # FAISS删除逻辑（效率较低）
            config.logger.info(f"Deleting document with doc_id: {doc_id} from FAISS")  # 记录删除操作
            self._delete_document_faiss(doc_id)  # 调用 FAISS 删除方法

    def _delete_document_fallback(self, doc_id: int):  # 定义备用删除方法的私有方法
        """备用删除方法：通过查询找到ID然后删除"""  # 方法的 docstring
        try:
            # 先搜索包含该doc_id的文档
            filter_dict = {"doc_id": doc_id}  # 构建过滤条件
            docs_to_delete = self.search("", k=1000, filter_dict=filter_dict)  # 搜索匹配的文档

            if not docs_to_delete:  # 如果没有找到
                config.logger.info(f"No documents found with doc_id: {doc_id}")  # 记录未找到
                return  # 返回

            # 提取文档ID（假设metadata中有唯一ID）
            ids_to_delete = []  # 待删除的 ID 列表
            for doc in docs_to_delete:  # 遍历找到的文档
                if 'chunk_id' in doc.metadata:  # 如果元数据中有 chunk_id
                    ids_to_delete.append(doc.metadata['chunk_id'])  # 添加到删除列表

            if ids_to_delete:  # 如果有可删除的 ID
                # 执行删除
                self.vector_store.delete(ids=ids_to_delete)  # 按 ID 批量删除
                config.logger.info(f"Deleted {len(ids_to_delete)} chunks for doc_id {doc_id}")  # 记录删除数量
            else:
                config.logger.info(f"No deletable chunks found for doc_id {doc_id}")  # 记录无可删除项

        except Exception as e:
            config.logger.error(f"Fallback delete failed: {e}")  # 记录错误

    def _delete_document_faiss(self, doc_id: int):  # 定义 FAISS 删除实现的私有方法
        """FAISS删除实现（需要重建索引）"""  # 方法的 docstring
        try:
            # 找到所有 metadata['doc_id'] == doc_id 的 ID
            ids_to_delete = []  # 待删除的 ID 列表
            for doc_uuid, doc in self.vector_store.docstore._dict.items():  # 遍历 FAISS 文档存储中的所有文档，.items() 返回 (key, value) 对
                if doc.metadata.get('doc_id') == doc_id:  # 如果文档的 doc_id 匹配
                    ids_to_delete.append(doc_uuid)  # 添加文档 UUID 到删除列表

            if ids_to_delete:  # 如果有要删除的文档
                # FAISS的delete方法可能不彻底，这里尝试删除
                self.vector_store.delete(ids_to_delete)  # 执行删除
                self.vector_store.save_local(self.persist_directory)  # 保存到磁盘
                config.logger.info(f"Deleted {len(ids_to_delete)} chunks for doc_id {doc_id}")  # 记录删除数量

                # 建议：定期重建FAISS索引以提高效率
                if len(ids_to_delete) > 100:  # 如果删除数量较大
                    config.logger.warning("Large deletion in FAISS. Consider rebuilding index for better performance.")  # 建议重建索引
            else:
                config.logger.info(f"No chunks found for doc_id {doc_id}")  # 记录未找到

        except Exception as e:
            config.logger.error(f"Failed to delete document from FAISS: {e}")  # 记录错误

    def delete_collection(self):  # 定义删除整个向量库的方法
        """
        删除整个向量库 (慎用)
        """
        if self.use_milvus:  # 如果使用 Milvus
            try:
                # 删除Milvus集合
                utility.drop_collection(self.collection_name)  # 删除整个集合（类似 DROP TABLE）
                config.logger.info(f"Successfully deleted Milvus collection '{self.collection_name}'")  # 记录成功
            except Exception as e:
                config.logger.error(f"Failed to delete Milvus collection: {e}")  # 记录错误
        else:  # 使用 FAISS
            # 删除FAISS目录
            if os.path.exists(self.persist_directory):  # 如果目录存在
                shutil.rmtree(self.persist_directory)  # 递归删除目录及所有内容
            self.vector_store = None  # 重置向量存储
            config.logger.info("Successfully deleted FAISS collection")  # 记录成功

    def get_stats(self) -> Dict[str, Any]:  # 定义获取向量库统计信息的方法
        """获取向量库统计信息"""  # 方法的 docstring
        stats = {  # 初始化统计信息字典
            "using_milvus": self.use_milvus,  # 是否使用 Milvus
            "collection_name": self.collection_name if self.use_milvus else None,  # 集合名称（Milvus 时有效）
            "persist_directory": self.persist_directory if not self.use_milvus else None,  # 持久化目录（FAISS 时有效）
        }

        if self.use_milvus and self.vector_store:  # Milvus 且已初始化
            try:
                # 获取Milvus集合信息
                collection_stats = utility.get_collection_stats(self.collection_name)  # 获取集合统计信息
                stats.update({  # 更新统计字典
                    "row_count": collection_stats.get("row_count", 0),  # 行数（文档数）
                    "partitions": collection_stats.get("partitions", []),  # 分区列表
                })
            except Exception as e:
                stats["error"] = f"Failed to get Milvus stats: {e}"  # 记录错误信息
        elif not self.use_milvus and self.vector_store:  # FAISS 且已初始化
            # FAISS统计
            stats["doc_count"] = len(self.vector_store.docstore._dict) if hasattr(self.vector_store, 'docstore') else 0  # hasattr 检查是否有 docstore 属性，有则统计文档数

        return stats  # 返回统计信息

    def migrate_faiss_to_milvus(self):  # 定义从 FAISS 迁移数据到 Milvus 的方法
        """将FAISS数据迁移到Milvus"""  # 方法的 docstring
        if not self.use_milvus or self.vector_store is None:  # 如果不使用 Milvus 或向量库未初始化
            config.logger.warning("Cannot migrate: not using Milvus or no vector store")  # 记录警告
            return False  # 返回失败

        try:
            config.logger.info("Starting migration from FAISS to Milvus...")  # 记录开始迁移

            # 1. 加载FAISS数据
            if os.path.exists(self.persist_directory):  # 如果 FAISS 持久化目录存在
                faiss_store = FAISS.load_local(self.persist_directory, self.embeddings, allow_dangerous_deserialization=True)  # 加载 FAISS 索引

                # 2. 提取所有文档
                all_docs = []  # 初始化文档列表
                for doc_uuid, doc in faiss_store.docstore._dict.items():  # 遍历 FAISS 文档存储
                    all_docs.append(doc)  # 添加到列表

                # 3. 添加到Milvus
                if all_docs:  # 如果有文档
                    self.add_documents(all_docs)  # 将所有文档添加到 Milvus
                    config.logger.info(f"Migrated {len(all_docs)} documents from FAISS to Milvus")  # 记录迁移数量

                    # 4. 备份原FAISS数据
                    backup_dir = self.persist_directory + "_migrated_backup"  # 备份目录路径
                    if os.path.exists(backup_dir):  # 如果备份目录已存在
                        shutil.rmtree(backup_dir)  # 删除旧备份
                    shutil.move(self.persist_directory, backup_dir)  # 将原 FAISS 数据移动到备份目录
                    config.logger.info(f"Backed up FAISS data to {backup_dir}")  # 记录备份位置

                    return True  # 返回成功

            return False  # 没有数据可迁移，返回 False

        except Exception as e:
            config.logger.error(f"Migration failed: {e}")  # 记录迁移失败
            return False  # 返回失败


# 创建单例实例
vector_store_manager = VectorStoreManager()  # 模块级别创建向量存储管理器的全局单例

# 导出（保持兼容性，同时保留完整管理器）
vector_store = vector_store_manager  # 创建别名，方便其他模块通过 vector_store 直接使用
