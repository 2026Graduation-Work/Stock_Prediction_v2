"""호환용 진입점. 실제 PIT 무결성 검사는 experiments 모듈을 사용한다."""

from experiments.check_data_integrity import check_integrity

if __name__ == "__main__":
    check_integrity()
