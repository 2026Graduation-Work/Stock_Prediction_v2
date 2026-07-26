# 비교실험 결과 연결

PR #16 비교실험 러너가 생성한 `comparison_results.json`을 이 디렉토리에 두면
`/performance`가 빌드 시 자동으로 읽습니다.

```text
frontend/artifacts/performance/comparison_results.json
```

- 파일이 없으면 화면 검증용 목데이터와 `샘플 데이터` 배지를 사용합니다.
- 파일이 존재하지만 JSON 구조나 B-A 델타가 잘못되면 빌드를 실패시킵니다.
- 같은 디렉토리의 다른 결과 파일을 사용할 때는 서버 전용
  `PERFORMANCE_RESULTS_FILE`에 파일명을 설정합니다.
- 러너의 `manifest.json`과 원본 CSV는 재현성 증빙을 위해 실험 결과 저장소에 함께 보관합니다.
