# Chart Colab notebooks

[`chart_holdout_2025_colab.ipynb`](chart_holdout_2025_colab.ipynb)는 최종 chart
baseline 두 개를 Colab CPU/고용량 RAM에서 실행하는 인수인계 노트북이다.

실행 전 준비물:

1. 팀 Drive에 `data/processed/*.parquet` 구조의 디렉터리 또는 그 디렉터리를 담은
   `.tar.gz` 스냅샷을 올린다.
2. 노트북의 `REPO_URL`, merge된 `COMMIT_SHA`, `DRIVE_ROOT`, `DATA_SOURCE`를 수정한다.
3. Colab에서 런타임을 고용량 RAM으로 선택하고 위에서 아래로 실행한다.

노트북은 H5/H20 라벨 생성에 쓸 수 있는 학습·평가 행 수를 종목별로 검사한다.
미래 관측이 부족하면 종목 전체를 버리지 않고 기존 loader 규칙대로 마지막 H5=13행,
H20=50행의 불완전한 tail만 제외한다. 따라서 2024-12-30 KOSPI 스냅샷의 상장폐지
종목도 폐지 전 유효한 2025 평가행은 유지한다. 적격 여부와 실제 labelable 행 수는
`coverage_preflight.csv`에 남고, 적격 종목이 없으면 학습 전에 실패한다. 실행 결과는
commit별 Drive 출력 폴더에 모델, 예측,
공용 ML 평가, 공용 백테스트, 실행 config, manifest와 `SHA256SUMS`로 저장된다.

중간 모델·예측 cache도 Drive에 두므로 Colab 연결이 끊긴 뒤 같은 commit과 data로
재실행하면 완료된 cache를 재사용할 수 있다. 기존 export 폴더는 자동으로
덮어쓰지 않는다.
