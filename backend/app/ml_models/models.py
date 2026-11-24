import warnings
import numpy as np
import xgboost as xgb
from sklearn.base import ClassifierMixin, BaseEstimator
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, VotingClassifier, StackingClassifier

warnings.filterwarnings("ignore")

class WrappedXGBClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, n_estimators=40, max_depth=4, learning_rate=0.1, random_state=42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state
        self.clf = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=self.random_state,
            eval_metric="logloss",
            n_jobs=-1
        )
        self.encoder = LabelEncoder()

    def fit(self, X, y):
        y_enc = self.encoder.fit_transform(y)
        self.clf.fit(X, y_enc)
        self.classes_ = self.encoder.classes_
        return self

    def predict(self, X):
        preds = self.clf.predict(X)
        return self.encoder.inverse_transform(preds)

    def predict_proba(self, X):
        return self.clf.predict_proba(X)

def get_all_models():
    """Returns all models: Base, XGBoost, Ensemble (Voting), and Meta Model (Stacking)."""
    lr = LogisticRegression(C=1.0, max_iter=200, solver="lbfgs", random_state=42)
    svm = CalibratedClassifierCV(LinearSVC(dual=False, max_iter=2000, random_state=42))
    rf = RandomForestClassifier(n_estimators=40, max_depth=10, n_jobs=-1, random_state=42)
    xgb_clf = WrappedXGBClassifier(n_estimators=40, max_depth=4, learning_rate=0.1, random_state=42)

    # Ensemble Model: Soft Voting across Logistic Regression, Random Forest, and XGBoost
    ensemble_clf = VotingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("xgb", xgb_clf)],
        voting="soft"
    )

    # Meta Model: Stacking Classifier with Logistic Regression as the Meta-Learner
    meta_clf = StackingClassifier(
        estimators=[("lr", lr), ("rf", rf), ("xgb", xgb_clf)],
        final_estimator=LogisticRegression(random_state=42),
        cv=2,
        n_jobs=-1
    )

    return {
        "Logistic Regression": lr,
        "Support Vector Machine": svm,
        "Random Forest": rf,
        "XGBoost": xgb_clf,
        "Ensemble (Voting)": ensemble_clf,
        "Meta Model (Stacking)": meta_clf
    }
