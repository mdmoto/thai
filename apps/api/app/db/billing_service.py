"""Credit pricing, purchase orders, deductions, and failure refunds."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
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
    "PREVIEW": "free_preview_runs_balance",
    "BASIC_DECISION": "basic_decision_runs_balance",
    "PROFESSIONAL": "deep_decision_runs_balance",
}

PAYMENT_METHODS: Dict[str, Dict[str, Any]] = {
    "ALIPAY": {
        "code": "ALIPAY",
        "name": "支付宝收款码",
        "image_url": "/payments/alipay-qr.png",
        "package_codes": ["STARTER", "GROWTH", "SCALE"],
    },
    "WECHAT_PAY": {
        "code": "WECHAT_PAY",
        "name": "微信收款码",
        "image_url": "/payments/wechat-pay-qr.png",
        "package_codes": ["STARTER", "GROWTH", "SCALE"],
    },
    "WECHAT_APPRECIATION": {
        "code": "WECHAT_APPRECIATION",
        "name": "微信赞赏码",
        "image_url": "/payments/wechat-appreciation-qr.png",
        "package_codes": ["BASIC_DECISION_SINGLE"],
    },
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
        "manual_payment": {
            "enabled": True,
            "automatic_callback": False,
            "methods": list(PAYMENT_METHODS.values()),
            "notice": (
                "扫码付款后提交付款信息，订单进入人工核验；"
                "只有管理员确认实际到账后才会发放次数和赠送积分。"
            ),
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
        field_column = getattr(User, entitlement_field)
        updated = (
            db.query(User)
            .filter(
                User.id == user.id,
                field_column >= 1,
            )
            .update(
                {field_column: field_column - 1},
                synchronize_session=False,
            )
        )
        if updated != 1:
            if plan_code == "PREVIEW":
                detail = (
                    "每个账号包含 1 次免费预览，当前免费次数已使用。"
                    "基础模拟需要 5 积分。"
                )
            else:
                detail = (
                    f"运行{RUN_LABELS.get(plan_code, plan_code)}需要 1 次可用次数，"
                    "当前可用次数为 0。请先购买对应决策套餐。"
                )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=detail,
            )
        db.expire_all()
        locked_user = db.query(User).filter(User.id == user.id).one()
        new_balance = int(getattr(locked_user, entitlement_field) or 0)
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
        db.flush()
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

    updated = (
        db.query(User)
        .filter(
            User.id == user.id,
            User.credits_balance >= cost,
        )
        .update(
            {User.credits_balance: User.credits_balance - cost},
            synchronize_session=False,
        )
    )
    if updated != 1:
        current_balance = int(
            db.query(User.credits_balance)
            .filter(User.id == user.id)
            .scalar()
            or 0
        )
        run_label = RUN_LABELS.get(plan_code, plan_code)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"运行{run_label}需要 {cost} 积分，当前余额为 "
                f"{current_balance} 积分。"
            ),
        )
    db.expire_all()
    locked_user = db.query(User).filter(User.id == user.id).one()
    transaction = CreditTransaction(
        user_id=locked_user.id,
        amount=-cost,
        transaction_type="RUN_RESERVATION",
        description=f"运行{RUN_LABELS.get(plan_code, plan_code)}",
        reference_id=f"reserve:{reference_id}",
        balance_after=locked_user.credits_balance,
    )
    db.add(transaction)
    db.flush()
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
    db.flush()


def allowed_payment_methods(package_code: str) -> list[Dict[str, Any]]:
    normalized = package_code.strip().upper()
    return [
        dict(method)
        for method in PAYMENT_METHODS.values()
        if normalized in method["package_codes"]
    ]


def submit_manual_payment(
    db: Session,
    *,
    order: PurchaseOrder,
    payment_method: str,
    payer_name: str | None,
    payment_claim_reference: str | None,
    payment_time_text: str | None,
    payment_claim_note: str | None,
) -> PurchaseOrder:
    """Record a customer's payment claim without granting any balance."""
    if order.status == "PAID":
        raise HTTPException(status_code=409, detail="订单已经完成入账")
    if order.status not in {
        "PENDING_PAYMENT",
        "PAYMENT_REVIEW",
        "PAYMENT_REJECTED",
    }:
        raise HTTPException(status_code=409, detail="订单状态不允许提交付款信息")
    normalized_method = payment_method.strip().upper()
    allowed_codes = {
        method["code"] for method in allowed_payment_methods(order.package_code)
    }
    if normalized_method not in allowed_codes:
        raise HTTPException(
            status_code=400,
            detail="该套餐不支持所选收款方式",
        )
    order.payment_method = normalized_method
    order.payer_name = payer_name
    order.payment_claim_reference = payment_claim_reference
    order.payment_time_text = payment_time_text
    order.payment_claim_note = payment_claim_note
    order.payment_claimed_at = datetime.utcnow()
    order.reviewed_at = None
    order.review_note = None
    order.status = "PAYMENT_REVIEW"
    db.commit()
    db.refresh(order)
    return order


def reject_manual_payment(
    db: Session,
    *,
    order_id: str,
    review_note: str,
) -> PurchaseOrder:
    order = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status == "PAID":
        raise HTTPException(status_code=409, detail="已入账订单不能退回核验")
    if order.status not in {"PAYMENT_REVIEW", "PENDING_PAYMENT"}:
        raise HTTPException(status_code=409, detail="订单状态不允许退回")
    order.status = "PAYMENT_REJECTED"
    order.reviewed_at = datetime.utcnow()
    order.review_note = review_note
    db.commit()
    db.refresh(order)
    return order


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
        if order.payment_reference != payment_reference:
            raise HTTPException(
                status_code=409,
                detail="该订单已使用其他付款凭证完成入账",
            )
        return order
    if order.status not in {
        "PENDING_PAYMENT",
        "PAYMENT_REVIEW",
        "PAYMENT_REJECTED",
    }:
        raise HTTPException(status_code=409, detail="订单状态不允许入账")
    duplicate_reference = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.payment_reference == payment_reference,
            PurchaseOrder.id != order.id,
        )
        .first()
    )
    if duplicate_reference:
        raise HTTPException(
            status_code=409,
            detail="该付款凭证编号已用于其他订单，请核对后重新提交",
        )

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
    order.reviewed_at = datetime.utcnow()
    order.review_note = "管理员确认实际到账"
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
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="该付款凭证编号已用于其他订单，请核对后重新提交",
        ) from error
    db.refresh(order)
    return order


def grant_admin_entitlements(
    db: Session,
    *,
    email: str,
    credits: int,
    basic_decision_runs: int,
    deep_decision_runs: int,
    reason: str,
) -> User:
    """Grant non-revenue internal/demo capacity with an auditable ledger trail."""
    user = (
        db.query(User)
        .filter(User.email == email.strip().lower())
        .with_for_update()
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="未找到指定账号")

    grant_reference = f"admin-grant:{uuid.uuid4().hex}"
    normalized_reason = reason.strip()
    if credits:
        user.credits_balance = int(user.credits_balance) + int(credits)
        db.add(
            CreditTransaction(
                user_id=user.id,
                amount=int(credits),
                transaction_type="ADMIN_COMP",
                description=f"管理员赠送额度：{normalized_reason}",
                reference_id=f"{grant_reference}:credits",
                balance_after=int(user.credits_balance),
            )
        )

    for plan_code, quantity, field in (
        (
            "BASIC_DECISION",
            int(basic_decision_runs),
            "basic_decision_runs_balance",
        ),
        (
            "PROFESSIONAL",
            int(deep_decision_runs),
            "deep_decision_runs_balance",
        ),
    ):
        if not quantity:
            continue
        new_balance = int(getattr(user, field) or 0) + quantity
        setattr(user, field, new_balance)
        db.add(
            RunEntitlementTransaction(
                user_id=user.id,
                plan_code=plan_code,
                amount=quantity,
                transaction_type="ADMIN_COMP",
                description=f"管理员赠送次数：{normalized_reason}",
                reference_id=f"{grant_reference}:{plan_code}",
                balance_after=new_balance,
            )
        )
    db.commit()
    db.refresh(user)
    return user
