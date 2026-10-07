"""One command to refresh the whole system (PHASE 11 - integration).

    raw files -> ETL -> warehouse -> ML scoring -> (dashboard and agent pick it up)

    python run_pipeline.py                 # load new/changed files, re-score students
    python run_pipeline.py --retrain       # ... and retrain the models
    python run_pipeline.py --new-semester  # simulate the arrival of a new semester first
    python run_pipeline.py --rebuild       # drop the database and rebuild everything

The dashboard notices the new ETL run / scoring time on its own and reloads.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import config
import etl_pipeline
import risk_model


def step(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--retrain", action="store_true", help="retrain the ML models")
    ap.add_argument("--new-semester", action="store_true",
                    help="generate one more semester of synthetic data before loading")
    ap.add_argument("--rebuild", action="store_true", help="drop the database and reload everything")
    args = ap.parse_args()
    t0 = time.time()
    py = [sys.executable]

    if args.new_semester:
        step("1/3  New data arrives (synthetic next semester)")
        subprocess.run(py + [str(config.DATA_DIR / "generate_data.py"), "--next-semester"], check=True)

    step("2/3  ETL: raw files -> staging -> data warehouse")
    if args.rebuild:
        etl_pipeline.drop_database()
    result = etl_pipeline.run(full=args.rebuild)
    if result["status"] != "SUCCESS":
        print("ETL failed - ML scoring skipped.")
        return 1

    step("3/3  Machine learning")
    if args.retrain or args.rebuild or not risk_model.MODEL_FILE.exists():
        subprocess.run(py + [str(Path(config.ML_DIR) / "train_model.py")], check=True)
    else:
        scored = risk_model.score_students(config.get_engine())
        print(f"re-scored {len(scored):,} active students with the existing model "
              f"({scored['RiskLevel'].isin(['Yuqori', 'Kritik']).sum():,} high or critical)")

    print(f"\nPipeline finished in {time.time() - t0:.0f}s. The dashboard will refresh automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
