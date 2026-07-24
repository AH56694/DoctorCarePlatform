from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the local PyTorch recruitment recommender."
    )
    parser.add_argument("--database-url", default="")
    parser.add_argument(
        "--output",
        default=".local-models/recruitment_recommender.pt",
    )
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260723)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from backend.app.db.session import SessionLocal
    from backend.app.recommendation.training import train_recruitment_model

    db = SessionLocal()
    try:
        result = train_recruitment_model(
            db,
            args.output,
            epochs=args.epochs,
            embedding_dim=args.embedding_dim,
            seed=args.seed,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
