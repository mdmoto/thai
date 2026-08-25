"""Privacy-first readiness checks for customer calibration CSV files."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

DATASET_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "observed_choices": {
        "required": ("choice_set_id", "alternative", "chosen"),
        "minimum_rows": 40,
        "minimum_groups": 20,
        "group_field": "choice_set_id",
        "purpose": "conditional_choice_fit",
    },
    "conversion_funnel": {
        "required": (
            "session_id",
            "occurred_at",
            "sku",
            "offered_price_thb",
            "channel",
            "converted",
        ),
        "minimum_rows": 200,
        "purpose": "conversion_and_price_response_fit",
    },
    "transactions": {
        "required": (
            "transaction_id",
            "occurred_at",
            "sku",
            "units",
            "net_revenue_thb",
            "channel",
            "province",
        ),
        "minimum_rows": 100,
        "purpose": "descriptive_sales_and_repeat_panel",
    },
    "venue_history": {
        "required": ("location_label", "date", "visits"),
        "minimum_rows": 30,
        "purpose": "venue_history_backtest",
    },
    "human_survey": {
        "required": (
            "respondent_id",
            "survey_date",
            "province",
            "age_band",
            "income_band",
            "question_id",
            "answer_code",
        ),
        "minimum_rows": 100,
        "purpose": "human_validation_and_attitude_tracking",
    },
}

DIRECT_PII_FIELDS = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "email",
    "email_address",
    "phone",
    "phone_number",
    "mobile",
    "address",
    "street_address",
    "national_id",
    "passport",
    "passport_number",
    "line_id",
    "facebook_id",
    "x_handle",
    "ip_address",
    "device_id",
}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{7,}$")
CHOICE_FEATURES = {
    "price_log_ratio",
    "affordability",
    "quality_fit",
    "brand_trust",
    "review_proof",
    "novelty",
    "convenience",
    "social_influence",
    "category_engagement",
    "localization",
    "distance_friction",
}


class CustomerDataError(ValueError):
    """Raised when a customer dataset is unsafe or structurally invalid."""


def read_csv_rows(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = [str(field or "").strip() for field in (reader.fieldnames or [])]
        rows = [dict(row) for row in reader]
    if not fields:
        raise CustomerDataError("CSV 缺少表头。")
    return fields, rows


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def validate_customer_rows(
    dataset_type: str,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if dataset_type not in DATASET_SCHEMAS:
        raise CustomerDataError(f"不支持的数据类型：{dataset_type}")
    schema = DATASET_SCHEMAS[dataset_type]
    normalized_fields = [str(field).strip() for field in fields]
    field_set = set(normalized_fields)
    missing = sorted(set(schema["required"]) - field_set)
    pii_fields = sorted(field_set & DIRECT_PII_FIELDS)
    empty_required = Counter()
    suspected_pii_cells: List[Dict[str, Any]] = []

    for row_number, row in enumerate(rows, start=2):
        for field in schema["required"]:
            if not str(row.get(field) or "").strip():
                empty_required[field] += 1
        for field, raw_value in row.items():
            value = str(raw_value or "").strip()
            if not value or field in DIRECT_PII_FIELDS:
                continue
            if EMAIL_PATTERN.match(value) or (
                "phone" in field.lower() and PHONE_PATTERN.match(value)
            ):
                suspected_pii_cells.append(
                    {"row": row_number, "field": field, "reason": "direct_identifier"}
                )
                if len(suspected_pii_cells) >= 20:
                    break

    choice_issues: List[str] = []
    group_count = 0
    usable_choice_features: List[str] = []
    if dataset_type == "observed_choices" and not missing:
        grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get("choice_set_id") or "")].append(row)
        grouped.pop("", None)
        group_count = len(grouped)
        for group_id, group_rows in grouped.items():
            chosen_count = sum(_truthy(row.get("chosen")) for row in group_rows)
            if len(group_rows) < 2:
                choice_issues.append(f"{group_id}: 少于两个备选项")
            if chosen_count != 1:
                choice_issues.append(f"{group_id}: chosen 必须且只能有一行")
            if len(choice_issues) >= 20:
                break
        for field in sorted(field_set & CHOICE_FEATURES):
            values = [str(row.get(field) or "").strip() for row in rows]
            if not all(values):
                continue
            try:
                numeric_values = [float(value) for value in values]
            except ValueError:
                choice_issues.append(f"{field}: 包含非数字值")
                continue
            if len(set(numeric_values)) > 1:
                usable_choice_features.append(field)
        if not usable_choice_features:
            choice_issues.append("至少需要一个完整且在备选项之间变化的模型特征")

    row_count = len(rows)
    threshold_met = row_count >= int(schema["minimum_rows"])
    minimum_groups = schema.get("minimum_groups")
    if dataset_type == "observed_choices":
        minimum_groups = max(20, len(usable_choice_features) * 5)
    if minimum_groups:
        threshold_met = threshold_met and group_count >= int(minimum_groups)
    safe = not pii_fields and not suspected_pii_cells
    structurally_valid = not missing and not empty_required and not choice_issues
    ready = safe and structurally_valid and threshold_met
    status = "ready_for_import" if ready else "needs_action"
    if dataset_type == "transactions" and ready:
        status = "descriptive_only_ready"

    return {
        "schema_version": "1",
        "dataset_type": dataset_type,
        "purpose": schema["purpose"],
        "status": status,
        "safe_to_import": safe,
        "ready_for_model_use": ready and dataset_type != "transactions",
        "descriptive_only": dataset_type == "transactions",
        "row_count": row_count,
        "group_count": group_count or None,
        "minimum_rows": schema["minimum_rows"],
        "minimum_groups": minimum_groups,
        "usable_choice_features": usable_choice_features,
        "missing_fields": missing,
        "empty_required_fields": dict(empty_required),
        "direct_pii_fields": pii_fields,
        "suspected_pii_cells": suspected_pii_cells,
        "choice_set_issues": choice_issues,
        "notes": (
            [
                "订单表只能用于描述销售、价格和复购；若要估计转化率，必须同时提供未购买的曝光/会话记录。"
            ]
            if dataset_type == "transactions"
            else []
        ),
    }


def validate_customer_csv(dataset_type: str, path: Path) -> Dict[str, Any]:
    fields, rows = read_csv_rows(path)
    report = validate_customer_rows(dataset_type, fields, rows)
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        **report,
        "file_name": path.name,
        "sha256": content_hash,
    }


def write_validation_report(report: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
