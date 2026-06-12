import os
import gc
import lightgbm as lgb
import pandas as pd
from sklearn.utils.class_weight import compute_sample_weight
from .base_model import BaseModel

class LGBMWrapper(BaseModel):
    def __init__(self, config: dict):
        super().__init__(config)
        self.params = config.get('model', {}).get('params', {})
        # 현재 파일(lgbm_wrapper.py)의 절대경로 기준 cache 디렉토리 지정
        CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(CURRENT_DIR, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _build_dataset(self, X, y, bin_path: str):
        """ DataFrame을 lgb.Dataset(.bin)으로 변환하고 캐싱합니다. """
        if os.path.exists(bin_path):
            print(f"  [CACHE HIT] 기존 캐시된 .bin 파일 로드 (1초 컷): {os.path.basename(bin_path)}")
            return lgb.Dataset(bin_path, free_raw_data=False)

        print(f"  [BUILD] 새로운 .bin 파일 굽는 중... (Shape: {X.shape})")
        sample_weights = compute_sample_weight("balanced", y)
        
        dataset = lgb.Dataset(
            X,
            label=y,
            weight=sample_weights,
            free_raw_data=False
        )
        dataset.construct()
        
        tmp_path = bin_path + ".tmp"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        
        dataset.save_binary(tmp_path)
        os.replace(tmp_path, bin_path)
        
        return dataset
        
    def fit(self, X_train, y_train, X_val=None, y_val=None, cache_hash=None):
        if isinstance(X_train, lgb.Dataset):
            print("[LGBM] 사전 생성된 Train/Validation 데이터셋 수신 완료.")
            train_data = X_train
            valid_data = y_train
        else:
            if cache_hash is None:
                cache_hash = "default_hash"
                
            train_bin_path = os.path.join(self.cache_dir, f"{cache_hash}_train.bin")
            print("[LGBM] Train 데이터셋 준비 중...")
            train_data = self._build_dataset(X_train, y_train, train_bin_path)
            
            del X_train, y_train
            gc.collect()

            valid_data = None
            if X_val is not None and y_val is not None:
                print("[LGBM] Validation 데이터셋 준비 중 (bin mapper 동기화)...")
                sample_weights_val = compute_sample_weight("balanced", y_val)
                valid_data = lgb.Dataset(
                    X_val,
                    label=y_val,
                    weight=sample_weights_val,
                    reference=train_data,
                    free_raw_data=False
                )
                del X_val, y_val
                gc.collect()

        print("[LGBM] 🚀 모델 학습 시작...")
        
        default_params = {
            'objective': 'multiclass',
            'num_class': 3,
            'metric': 'multi_logloss',
            'boosting_type': 'gbdt',
            'random_state': 42,
            'verbose': -1,
            'n_jobs': -1
        }
        lgb_params = {**default_params, **self.params}
        n_estimators = lgb_params.pop('n_estimators', 1000)

        callbacks = []
        if valid_data:
            callbacks.append(lgb.early_stopping(stopping_rounds=50, verbose=False))
            callbacks.append(lgb.log_evaluation(period=100))

        self.model = lgb.train(
            params=lgb_params,
            train_set=train_data,
            num_boost_round=n_estimators,
            valid_sets=[train_data, valid_data] if valid_data else [train_data],
            callbacks=callbacks
        )
        
        print("[LGBM] ✅ 학습 완료!")
        
        if cache_hash is not None:
            models_dir = os.path.join(self.cache_dir, "models")
            os.makedirs(models_dir, exist_ok=True)
            model_save_path = os.path.join(models_dir, f"{cache_hash}_model.txt")
            self.model.save_model(model_save_path)
            print(f"[LGBM] 모델 파라미터(Booster) 저장 완료 -> {model_save_path}")
            
        del train_data, valid_data
        gc.collect()

    def predict(self, X_test):
        if self.model is None:
            raise ValueError("모델이 학습되지 않았습니다. fit()을 먼저 호출하세요.")
        
        probs = self.model.predict(X_test)
        return probs[:, 2]
