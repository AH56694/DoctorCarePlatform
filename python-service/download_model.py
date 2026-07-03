"""
模型下载脚本 - 将 HuggingFace 模型下载到项目本地目录

使用方法：
    python download_model.py

下载完成后，在 .env 中设置：
    LOCAL_EMBEDDING_MODEL_PATH=./models/bge-small-zh-v1.5
"""

import os
import sys


def download_embedding_model():
    """下载 Embedding 模型到本地目录"""
    model_name = "BAAI/bge-small-zh-v1.5"  # HuggingFace 上的模型名称
    save_dir = os.path.join(os.path.dirname(__file__), "models", "bge-small-zh-v1.5")  # 保存到项目下的 models/bge-small-zh-v1.5 目录

    if os.path.exists(save_dir) and os.path.exists(os.path.join(save_dir, "config.json")):
        print(f"[跳过] 模型已存在于: {save_dir}")
        print(f"  请确保 .env 中 LOCAL_EMBEDDING_MODEL_PATH=./models/bge-small-zh-v1.5")
        return save_dir

    print(f"[下载] 正在下载 Embedding 模型: {model_name}")
    print(f"  保存到: {save_dir}")
    print(f"  模型大小约 90MB，请耐心等待...")

    os.makedirs(save_dir, exist_ok=True)  # 创建目录

    # 方式1：使用 huggingface_hub 下载（推荐，支持断点续传）
    try:
        from huggingface_hub import snapshot_download
        print("\n[方式1] 使用 huggingface_hub 下载...")
        downloaded_path = snapshot_download(
            repo_id=model_name,
            local_dir=save_dir,
            local_dir_use_symlinks=False  # 不使用符号链接，直接复制文件
        )
        print(f"[成功] 模型已下载到: {downloaded_path}")
        return downloaded_path
    except ImportError:
        print("[跳过] huggingface_hub 未安装，尝试其他方式...")
    except Exception as e:
        print(f"[警告] huggingface_hub 下载失败: {e}")
        print("  尝试使用 sentence-transformers 方式...")

    # 方式2：使用 sentence-transformers 下载并保存
    try:
        from sentence_transformers import SentenceTransformer
        print("\n[方式2] 使用 sentence-transformers 下载...")
        model = SentenceTransformer(model_name)
        model.save(save_dir)
        print(f"[成功] 模型已下载并保存到: {save_dir}")
        return save_dir
    except Exception as e:
        print(f"[失败] sentence-transformers 下载也失败: {e}")
        print("\n请尝试手动下载：")
        print(f"  1. 浏览器打开 https://huggingface.co/{model_name}/tree/main")
        print(f"  2. 下载所有文件到 {save_dir}")
        print(f"  3. 确保目录下有 config.json、model.safetensors 等文件")
        return None


def download_reranker_model():
    """下载 Reranker 模型到本地目录（可选，仅在使用 bge reranker 时需要）"""
    model_name = "BAAI/bge-reranker-base"
    save_dir = os.path.join(os.path.dirname(__file__), "models", "bge-reranker-base")

    if os.path.exists(save_dir) and os.path.exists(os.path.join(save_dir, "config.json")):
        print(f"\n[跳过] Reranker 模型已存在于: {save_dir}")
        return save_dir

    print(f"\n[可选] 是否下载 Reranker 模型 ({model_name})？")
    print(f"  仅在 .env 中 RERANKER_TYPE=bge 时需要")
    choice = input("  输入 y 下载，其他跳过: ").strip().lower()

    if choice != "y":
        print("  [跳过] Reranker 模型下载")
        return None

    print(f"[下载] 正在下载 Reranker 模型: {model_name}")
    print(f"  保存到: {save_dir}")

    os.makedirs(save_dir, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
        downloaded_path = snapshot_download(
            repo_id=model_name,
            local_dir=save_dir,
            local_dir_use_symlinks=False
        )
        print(f"[成功] Reranker 模型已下载到: {downloaded_path}")
        return downloaded_path
    except Exception as e:
        print(f"[失败] 下载失败: {e}")
        return None


def update_env_file(embedding_path, reranker_path=None):
    """自动更新 .env 文件中的模型路径配置"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")

    if not os.path.exists(env_path):
        print(f"\n[跳过] .env 文件不存在: {env_path}")
        return

    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 更新 Embedding 模型路径
    old_line = [line for line in content.split("\n") if line.startswith("LOCAL_EMBEDDING_MODEL_PATH=")]
    if old_line:
        # 替换已有行
        content = content.replace(old_line[0], f"LOCAL_EMBEDDING_MODEL_PATH={embedding_path}")
    else:
        # 在 LOCAL_EMBEDDING_MODEL 后面追加
        anchor = "LOCAL_EMBEDDING_MODEL="
        if anchor in content:
            # 找到该行并在其后插入
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.startswith(anchor):
                    new_lines.append(f"LOCAL_EMBEDDING_MODEL_PATH={embedding_path}")
            content = "\n".join(new_lines)
        else:
            content += f"\n\n# 本地Embedding模型磁盘路径\nLOCAL_EMBEDDING_MODEL_PATH={embedding_path}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n[配置] 已更新 .env: LOCAL_EMBEDDING_MODEL_PATH={embedding_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("  AI Knowledge System - 模型下载工具")
    print("=" * 60)

    # 下载 Embedding 模型
    embedding_path = download_embedding_model()

    # 更新 .env 配置
    if embedding_path:
        # 使用相对路径（相对于项目根目录）
        rel_path = "./models/bge-small-zh-v1.5"
        update_env_file(rel_path)

    # 可选：下载 Reranker 模型
    download_reranker_model()

    print("\n" + "=" * 60)
    print("  下载完成！")
    print("  启动服务时将直接从本地加载模型，无需联网。")
    print("=" * 60)
