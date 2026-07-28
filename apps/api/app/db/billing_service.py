"""Credit pricing, purchase orders, deductions, and failure refunds."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    CreditTransaction,
    PurchaseOrder,
    RunEntitlementTransaction,
    User,
)


CREDIT_PRICING = {
    "PREVIEW": 0,
    "STANDARD": 5,
    "BASIC_DECISION": 0,
    "PROFESSIONAL": 0,
    "DEEP": 60,
    "ENTERPRISE": 120,
}

ENTITLEMENT_FIELDS = {
    "BASIC_DECISION": "basic_decision_runs_balance",
    "PROFESSIONAL": "deep_decision_runs_balance",
}

PUBLIC_PLAN_CODES = (
    "PREVIEW",
    "STANDARD",
    "BASIC_DECISION",
    "PROFESSIONAL",
)

RUN_LABELS = {
    "PREVIEW": "免费预览",
    "STANDARD": "基础模拟",
    "BASIC_DECISION": "基础决策",
    "PROFESSIONAL": "深度决策",
    "DEEP": "专属研究",
    "ENTERPRISE": "企业定制",
}

PACKAGE_CATALOG: Dict[str, Dict[str, Any]] = {
    "BASIC_DECISION_SINGLE": {
        "code": "BASIC_DECISION_SINGLE",
        "name": "单次基础决策",
        "credits": 1,
        "bonus_credits": 1,
        "run_entitlements": {"BASIC_DECISION": 1},
        "amount_minor": 99_000,
        "currency": "THB",
        "description": (
            "含 1 次基础决策（20,000 人 AI 模拟消费人群），"
            "另赠 1 积分；赠送积分可累计用于基础模拟。"
        ),
    },
    "STARTER": {
        "code": "STARTER",
        "name": "单次专业决策包",
        "credits": 10,
        "bonus_credits": 10,
        "run_entitlements": {"PROFESSIONAL": 1},
        "amount_minor": 790_000,
        "currency": "THB",
        "description": (
            "含 1 次深度决策（300,000 人 AI 模拟消费人群），"
            "另赠 10 积分，可运行 2 次基础模拟。"
        ),
    },
    "GROWTH": {
        "code": "GROWTH",
        "name": "增长团队包",
        "credits": 50,
        "bonus_credits": 50,
        "run_entitlements": {"PROFESSIONAL": 5},
        "amount_minor": 3_490_000,
        "currency": "THB",
        "description": (
            "含 5 次深度决策，另赠 50 积分；"
            "赠送积分可运行 10 次基础模拟。"
        ),
    },
    "SCALE": {
        "code": "SCALE",
        "name": "规模化决策包",
        "credits": 200,
        "bonus_credits": 200,
        "run_entitlements": {"PROFESSIONAL": 15},
        "amount_minor": 8_900_000,
        "currency": "THB",
        "description": (
            "含 15 次深度决策，另赠 200 积分；"
            "赠送积分可运行 40 次基础模拟。"
        ),
    },
}


def public_catalog() -> Dict[str, Any]:
    return {
        "credit_pricing": {
            code: CREDIT_PRICING[code] for code in PUBLIC_PLAN_CODES
        },
        "packages": list(PACKAGE_CATALOG.values()),
        "self_service_plans": list(PUBLIC_PLAN_CODES),
        "assisted_plans": [],
        "billing_policy": {
            "PREVIEW": {"type": "free_account_allowance", "quantity": 1},
            "STANDARD": {"type": "credits", "credits_per_run": 5},
            "BASIC_DECISION": {
                "type": "run_entitlement",
                "entitlement_per_run": 1,
            },
            "PROFESSIONAL": {
                "type": "run_entitlement",
                "entitlement_per_run": 1,
            },
        },
    }


def create_purchase_order(
    db: Session,
    user: User,
    package_code: str,
) -> PurchaseOrder:
    normalized = package_code.strip().upper()
    package = PACKAGE_CATALOG.get(normalized)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未知积分套餐",
        )
    order = PurchaseOrder(
        user_id=user.id,
        package_code=normalized,
        credits=int(package["credits"]),
        entitlements_json=dict(package.get("run_entitlements") or {}),
        amount_minor=int(package["amount_minor"]),
        currency=str(package["currency"]),
        status="PENDING_PAYMENT",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def check_and_reserve_run(
    db: Session,
    user: User,
    plan_code: str,
    reference_id: str,
) -> Dict[str, Any]:
    """Atomically reserve either credits or one purchased decision run."""
    entitlement_field = ENTITLEMENT_FIELDS.get(plan_code)
    if entitlement_field:
        locked_user = (
            db.query(User)
            .filter(User.id == user.id)
            .with_for_update()
            .one()
        )
        balance = int(getattr(locked_user, entitlement_field) or 0)
        if balance < 1:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"运行{RUN_LABELS.get(plan_code, plan_code)}需要 1 次可用次数，"
                    "当前可用次数为 0。请先购买对应决策套餐。"
                ),
            )
        new_balance = balance - 1
        setattr(locked_user, entitlement_field, new_balance)
        db.add(
            RunEntitlementTransaction(
                user_id=locked_user.id,
                plan_code=plan_code,
                amount=-1,
                transaction_type="RUN_RESERVATION",
                description=f"运行{RUN_LABELS.get(plan_code, plan_code)}",
                reference_id=f"reserve:{reference_id}",
                balance_after=new_balance,
            )
        )
        db.commit()
        db.refresh(locked_user)
        return {
            "deducted": 0,
            "deducted_credits": 0,
            "entitlement_code": plan_code,
            "entitlement_deducted": 1,
            "remaining_credits": int(locked_user.credits_balance),
            "remaining_entitlements": new_balance,
            "reference_id": reference_id,
        }

    cost = int(CREDIT_PRICING.get(plan_code, 0))
    if cost == 0:
        return {
            "deducted": 0,
            "deducted_credits": 0,
            "entitlement_code": None,
            "entitlement_deducted": 0,
            "remaining_credits": int(user.credits_balance),
            "reference_id": reference_id,
        }

    locked_user = (
        db.query(User)
        .filter(User.id == user.id)
        .with_for_update()
        .one()
    )
    if int(locked_user.credits_balance) < cost:
        run_label = RUN_LABELS.get(plan_code, plan_code)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"运行{run_label}需要 {cost} 积分，当前余额为 "
                f"{locked_user.credits_balance} 积分。"
            ),
        )

    locked_user.credits_balance = int(locked_user.credits_balance) - cost
    transaction = CreditTransaction(
        user_id=locked_user.id,
        amount=-cost,
        transaction_type="RUN_RESERVATION",
        description=f"运行{RUN_LABELS.get(plan_code, plan_code)}",
        reference_id=f"reserve:{reference_id}",
        balance_after=locked_user.credits_balance,
    )
    db.add(transaction)
    db.commit()
    db.refresh(locked_user)
    return {
        "deducted": cost,
        "deducted_credits": cost,
        "entitlement_code": None,
        "entitlement_deducted": 0,
        "remaining_credits": int(locked_user.credits_balance),
        "reference_id": reference_id,
    }


def refund_run_reservation(
    db: Session,
    user_id: str,
    reservation: Dict[str, Any],
    reference_id: str,
) -> None:
    """Refund one failed run reservation exactly once."""
    amount = int(reservation.get("deducted_credits") or 0)
    entitlement_code = reservation.get("entitlement_code")
    entitlement_amount = int(reservation.get("entitlement_deducted") or 0)
    refund_reference = f"refund:{reference_id}"
    if entitlement_code and entitlement_amount > 0:
        existing = (
            db.query(RunEntitlementTransaction)
            .filter(
                RunEntitlementTransaction.reference_id == refund_reference
            )
            .first()
        )
    else:
        existing = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.reference_id == refund_reference)
            .first()
        )
    if existing:
        return
    if amount <= 0 and entitlement_amount <= 0:
        return
    locked_user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .one()
    )
    if entitlement_code and entitlement_amount > 0:
        field = ENTITLEMENT_FIELDS[str(entitlement_code)]
        new_balance = int(getattr(locked_user, field) or 0) + entitlement_amount
        setattr(locked_user, field, new_balance)
        db.add(
            RunEntitlementTransaction(
                user_id=user_id,
                plan_code=str(entitlement_code),
                amount=entitlement_amount,
                transaction_type="FAILED_RUN_REFUND",
                description="模拟失败，自动退回决策次数",
                reference_id=refund_reference,
                balance_after=new_balance,
            )
        )
    else:
        locked_user.credits_balance = (
            int(locked_user.credits_balance) + int(amount)
        )
        db.add(
            CreditTransaction(
                user_id=user_id,
                amount=int(amount),
                transaction_type="FAILED_RUN_REFUND",
                description="模拟失败，自动退回预留积分",
                reference_id=refund_reference,
                balance_after=locked_user.credits_balance,
            )
        )
    db.commit()


def complete_purchase_order(
    db: Session,
    order_id: str,
    payment_reference: str,
) -> PurchaseOrder:
    """Confirm an externally verified payment and grant credits once."""
    order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "PAID":
        return order
    if order.status != "PENDING_PAYMENT":
        raise HTTPException(status_code=409, detail="订单状态不允许入账")

    locked_user = (
        db.query(User)
        .filter(User.id == order.user_id)
        .with_for_update()
        .one()
    )
    locked_user.credits_balance = int(locked_user.credits_balance) + int(
        order.credits
    )
    package = PACKAGE_CATALOG.get(order.package_code, {})
    entitlement_source = (
        order.entitlements_json
        if order.entitlements_json is not None
        else package.get("run_entitlements")
    )
    entitlements = dict(entitlement_source or {})
    for plan_code, quantity in entitlements.items():
        field = ENTITLEMENT_FIELDS.get(str(plan_code))
        if not field:
            continue
        granted = max(0, int(quantity))
        if granted == 0:
            continue
        new_balance = int(getattr(locked_user, field) or 0) + granted
        setattr(locked_user, field, new_balance)
        db.add(
            RunEntitlementTransaction(
                user_id=locked_user.id,
                plan_code=str(plan_code),
                amount=granted,
                transaction_type="PURCHASE",
                description=f"订单 {order.id} 决策次数入账",
                reference_id=f"order:{order.id}:{plan_code}",
                balance_after=new_balance,
            )
        )
    order.status = "PAID"
    order.payment_reference = payment_reference
    if int(order.credits) > 0:
        db.add(
            CreditTransaction(
                user_id=locked_user.id,
                amount=int(order.credits),
                transaction_type="PURCHASE_BONUS",
                description=f"订单 {order.id} 赠送积分",
                reference_id=f"order:{order.id}",
                balance_after=locked_user.credits_balance,
            )
        )
    db.commit()
    db.refresh(order)
    return order
