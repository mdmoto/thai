"""Credit pricing, purchase orders, deductions, and failure refunds."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import CreditTransaction, PurchaseOrder, User


CREDIT_PRICING = {
    "PREVIEW": 0,
    "STANDARD": 5,
    "PROFESSIONAL": 20,
    "DEEP": 60,
    "ENTERPRISE": 120,
}

PUBLIC_PLAN_CODES = ("PREVIEW", "STANDARD", "PROFESSIONAL")

RUN_LABELS = {
    "PREVIEW": "免费预览",
    "STANDARD": "基础模拟",
    "PROFESSIONAL": "深度决策",
    "DEEP": "专属研究",
    "ENTERPRISE": "企业定制",
}

PACKAGE_CATALOG: Dict[str, Dict[str, Any]] = {
    "STARTER": {
        "code": "STARTER",
        "name": "单次专业决策包",
        "credits": 20,
        "amount_minor": 790_000,
        "currency": "THB",
        "description": "最多可运行 1 次深度决策，或 4 次基础模拟。",
    },
    "GROWTH": {
        "code": "GROWTH",
        "name": "增长团队包",
        "credits": 110,
        "amount_minor": 3_490_000,
        "currency": "THB",
        "description": "含 100 积分与 10 积分赠送；最多可运行 5 次深度决策加 2 次基础模拟，或 22 次基础模拟。",
    },
    "SCALE": {
        "code": "SCALE",
        "name": "规模化决策包",
        "credits": 360,
        "amount_minor": 8_900_000,
        "currency": "THB",
        "description": "含 300 积分与 60 积分赠送；最多可运行 18 次深度决策，或 72 次基础模拟，可自由组合。",
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
        amount_minor=int(package["amount_minor"]),
        currency=str(package["currency"]),
        status="PENDING_PAYMENT",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def check_and_deduct_credits(
    db: Session,
    user: User,
    plan_code: str,
    reference_id: str,
) -> Dict[str, Any]:
    """Atomically reserve credits for a run and return the deduction details."""
    cost = int(CREDIT_PRICING.get(plan_code, 0))
    if cost == 0:
        return {
            "deducted": 0,
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
        "remaining_credits": int(locked_user.credits_balance),
        "reference_id": reference_id,
    }


def refund_reserved_credits(
    db: Session,
    user_id: str,
    amount: int,
    reference_id: str,
) -> None:
    """Refund one failed run exactly once."""
    if amount <= 0:
        return
    refund_reference = f"refund:{reference_id}"
    existing = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.reference_id == refund_reference)
        .first()
    )
    if existing:
        return
    locked_user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .one()
    )
    locked_user.credits_balance = int(locked_user.credits_balance) + int(amount)
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
    locked_user.credits_balance = (
        int(locked_user.credits_balance) + int(order.credits)
    )
    order.status = "PAID"
    order.payment_reference = payment_reference
    db.add(
        CreditTransaction(
            user_id=locked_user.id,
            amount=int(order.credits),
            transaction_type="PURCHASE",
            description=f"订单 {order.id} 支付确认",
            reference_id=f"order:{order.id}",
            balance_after=locked_user.credits_balance,
        )
    )
    db.commit()
    db.refresh(order)
    return order
