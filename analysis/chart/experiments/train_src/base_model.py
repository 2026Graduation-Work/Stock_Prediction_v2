from abc import ABC, abstractmethod

class BaseModel(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.model = None

    @abstractmethod
    def fit(self, X_train, y_train, X_val=None, y_val=None, cache_hash=None):
        """
        모델 학습 (인터페이스 통일)
        - cache_hash: 데이터셋의 캐싱(저장/재사용)을 위한 고유 ID
        """
        pass

    @abstractmethod
    def predict(self, X_test):
        """
        모델 예측 (인터페이스 통일)
        """
        pass
