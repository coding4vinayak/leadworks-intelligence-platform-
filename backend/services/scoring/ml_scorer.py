"""Machine learning-based lead scoring using scikit-learn and XGBoost."""
import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import structlog

logger = structlog.get_logger()


class MLScorer:
    """
    ML-powered lead scoring using XGBoost/Random Forest.

    Features used for prediction:
    - Firmographic: title seniority, company size, industry
    - Behavioral: page visits, time on site, pages viewed
    - Engagement: emails opened, clicked, replied
    - Enrichment: data completeness, tech stack overlap
    - Temporal: time since last activity, day of week patterns

    Supports:
    - Training on historical conversion data
    - Feature importance analysis
    - Model versioning
    - A/B testing between models
    - Explainability (SHAP-like feature contributions)
    """

    # Feature definitions for the model
    FEATURE_COLUMNS = [
        # Firmographic
        "seniority_level",      # 0-5 encoded
        "company_size_bucket",  # 0-5 encoded
        "industry_match",       # 0 or 1
        "has_job_title",        # 0 or 1
        # Behavioral
        "page_visits",          # int
        "time_on_site_minutes", # float
        "visited_pricing",      # 0 or 1
        "visited_demo",         # 0 or 1
        "form_submissions",     # int
        "content_downloads",    # int
        # Engagement
        "emails_sent",          # int
        "emails_opened",        # int
        "emails_clicked",       # int
        "has_replied",          # 0 or 1
        "open_rate",            # float 0-1
        "click_rate",           # float 0-1
        # Enrichment quality
        "has_email",            # 0 or 1
        "has_phone",            # 0 or 1
        "has_linkedin",         # 0 or 1
        "has_company",          # 0 or 1
        "is_enriched",          # 0 or 1
        "data_completeness",    # float 0-1
        # Tech/ICP
        "tech_stack_match",     # float 0-1
        "icp_score",            # float 0-1
        # Temporal
        "days_since_created",   # int
        "days_since_last_activity", # int
        "is_return_visitor",    # 0 or 1
    ]

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = None
        self.feature_importances = {}
        self.model_version = "1.0"
        self.model_accuracy = 0.0

        if model_path and Path(model_path).exists():
            self.load_model(model_path)

    def train(
        self,
        training_data: List[Dict[str, Any]],
        labels: List[int],
        model_type: str = "xgboost",
        test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Train the scoring model on historical lead data.

        Args:
            training_data: List of lead dicts with features
            labels: 1 = converted, 0 = not converted
            model_type: "xgboost", "random_forest", "gradient_boosting"
            test_size: Fraction for test split

        Returns:
            Training metrics (accuracy, precision, recall, feature importances)
        """
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, roc_auc_score,
        )

        # Extract features
        X = np.array([self._extract_features(d) for d in training_data])
        y = np.array(labels)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        if model_type == "xgboost":
            import xgboost as xgb
            self.model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                eval_metric='logloss',
            )
        elif model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=10,
                random_state=42,
            )
        else:
            from sklearn.ensemble import GradientBoostingClassifier
            self.model = GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_prob = self.model.predict_proba(X_test_scaled)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "auc_roc": float(roc_auc_score(y_test, y_prob)),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "model_type": model_type,
        }

        # Feature importances
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            self.feature_importances = dict(zip(self.FEATURE_COLUMNS, importances.tolist()))
            metrics["top_features"] = sorted(
                self.feature_importances.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10]

        self.model_accuracy = metrics["accuracy"]
        self.model_version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        logger.info("ml_model_trained", metrics=metrics)
        return metrics

    def predict_score(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict conversion probability for a lead.

        Returns:
            {
                "score": 0-100,
                "probability": 0.0-1.0,
                "category": "hot|warm|cold",
                "feature_contributions": {...},
                "confidence": "high|medium|low"
            }
        """
        if self.model is None:
            logger.warning("ml_model_not_trained")
            return {"score": 0, "probability": 0, "category": "cold", "confidence": "low"}

        features = np.array([self._extract_features(lead_data)])

        if self.scaler:
            features = self.scaler.transform(features)

        # Get probability
        probability = float(self.model.predict_proba(features)[0][1])
        score = round(probability * 100, 1)

        # Category
        if score >= 75:
            category = "hot"
        elif score >= 45:
            category = "warm"
        else:
            category = "cold"

        # Feature contributions (simplified SHAP-like)
        contributions = self._get_feature_contributions(lead_data)

        return {
            "score": score,
            "probability": round(probability, 4),
            "category": category,
            "feature_contributions": contributions,
            "confidence": "high" if self.model_accuracy > 0.8 else "medium",
            "model_version": self.model_version,
        }

    def predict_batch(self, leads: List[Dict]) -> List[Dict]:
        """Score multiple leads at once (efficient batch prediction)."""
        if self.model is None:
            return [{"score": 0, "category": "cold"} for _ in leads]

        features = np.array([self._extract_features(l) for l in leads])
        if self.scaler:
            features = self.scaler.transform(features)

        probabilities = self.model.predict_proba(features)[:, 1]

        results = []
        for prob in probabilities:
            score = round(float(prob) * 100, 1)
            category = "hot" if score >= 75 else ("warm" if score >= 45 else "cold")
            results.append({"score": score, "probability": float(prob), "category": category})

        return results

    def _extract_features(self, lead: Dict) -> List[float]:
        """Extract ML features from lead data."""
        features = []

        # Seniority level (encoded)
        title = (lead.get("job_title") or "").lower()
        seniority = 0
        if any(t in title for t in ["ceo", "cto", "cfo", "founder", "chief"]):
            seniority = 5
        elif any(t in title for t in ["vp", "vice president"]):
            seniority = 4
        elif "director" in title:
            seniority = 3
        elif any(t in title for t in ["manager", "head"]):
            seniority = 2
        elif any(t in title for t in ["senior", "lead"]):
            seniority = 1
        features.append(seniority)

        # Company size bucket
        emp = lead.get("employee_count") or 0
        if emp >= 1000: size = 5
        elif emp >= 201: size = 4
        elif emp >= 51: size = 3
        elif emp >= 11: size = 2
        elif emp >= 1: size = 1
        else: size = 0
        features.append(size)

        # Binary flags
        features.append(1 if lead.get("industry_match") else 0)
        features.append(1 if lead.get("job_title") else 0)

        # Behavioral
        features.append(min(lead.get("page_visits") or 0, 100))
        features.append(min(lead.get("time_on_site_minutes") or 0, 60))
        intent = lead.get("intent_signals") or {}
        features.append(1 if intent.get("visited_pricing") else 0)
        features.append(1 if intent.get("visited_demo") else 0)
        features.append(min(intent.get("form_submissions") or 0, 10))
        features.append(min(intent.get("content_downloads") or 0, 10))

        # Engagement
        emails_sent = lead.get("emails_sent") or 0
        emails_opened = lead.get("emails_opened") or 0
        emails_clicked = lead.get("emails_clicked") or 0
        features.append(min(emails_sent, 20))
        features.append(min(emails_opened, 20))
        features.append(min(emails_clicked, 10))
        features.append(1 if lead.get("last_responded_at") else 0)
        features.append(emails_opened / max(emails_sent, 1))
        features.append(emails_clicked / max(emails_opened, 1))

        # Enrichment quality
        features.append(1 if lead.get("email") else 0)
        features.append(1 if lead.get("phone") else 0)
        features.append(1 if lead.get("linkedin_url") else 0)
        features.append(1 if lead.get("company_name") else 0)
        features.append(1 if lead.get("is_enriched") else 0)

        # Data completeness (count non-null fields)
        key_fields = ["email", "first_name", "last_name", "phone", "job_title",
                      "company_name", "city", "linkedin_url", "website", "industry"]
        filled = sum(1 for f in key_fields if lead.get(f))
        features.append(filled / len(key_fields))

        # Tech/ICP
        features.append(lead.get("tech_stack_match_score") or 0)
        features.append((lead.get("icp_score") or 0) / 100)

        # Temporal
        features.append(min(lead.get("days_since_created") or 0, 365))
        features.append(min(lead.get("days_since_last_activity") or 0, 90))
        features.append(1 if lead.get("is_return_visitor") else 0)

        return features

    def _get_feature_contributions(self, lead: Dict) -> Dict[str, float]:
        """Get approximate feature contributions to score."""
        if not self.feature_importances:
            return {}

        features = self._extract_features(lead)
        contributions = {}

        for col, val, importance in zip(self.FEATURE_COLUMNS, features, self.feature_importances.values()):
            contributions[col] = round(val * importance * 100, 2)

        # Sort by absolute contribution
        return dict(sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:10])

    def save_model(self, path: str):
        """Save trained model to disk."""
        data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_importances": self.feature_importances,
            "model_version": self.model_version,
            "model_accuracy": self.model_accuracy,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("model_saved", path=path)

    def load_model(self, path: str):
        """Load trained model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.feature_importances = data["feature_importances"]
        self.model_version = data["model_version"]
        self.model_accuracy = data["model_accuracy"]
        logger.info("model_loaded", path=path, version=self.model_version)
