"""외부 피처를 결합한 feature store를 생성하는 CLI."""

from __future__ import annotations

import argparse

import yaml

from .panel_builder import build_feature_store


def main() -> None:
    parser = argparse.ArgumentParser(description="외부 Parquet 피처를 processed 패널에 결합합니다.")
    parser.add_argument("--config", required=True, help="실험용 local.yaml 경로")
    parser.add_argument("--output", help="feature store 출력 경로; 없으면 config 값을 사용")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    manifest = build_feature_store(config, output_dir=args.output)
    print(f"feature store 생성 완료: {manifest['output_feature_store_dir']}")
    print(f"처리된 종목 파일 수: {len(manifest['files'])}")


if __name__ == "__main__":
    main()
