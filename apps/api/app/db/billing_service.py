"""
Billing & Credit Consumption Manager.
Manages credit recharges, subscription plan upgrades, and simulation deductions.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.db.models import User, CreditTransaction

CREDIT_PRICING = {
    "FREE": 0,             # 100 agents preview: 0 credits
    "PROFESSIONAL": 20,    # 30,000 agents run: 20 credits
    "ENTERPRISE": 80,      # 100,000+ agents run + Gemini 1.5 Pro: 80 credits
    "DEEP": 80,
}

def check_and_deduct_credits(db: Session, user: User, plan_code: str = "FREE") -> Dict[str, Any]:
    """
    Checks if user has sufficient credit balance and deducts credits for a simulation run.
    """
    cost = CREDIT_PRICING.get(plan_code, 0)
    if cost == 0:
        return {"deducted": 0, "remaining_credits": user.credits_balance}

    if user.credits_balance < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分余额不足！运行【{plan_code}】需要 {cost} 积分，您当前余额为 {user.credits_balance} 积分。请充值后继续。"
        )

    user.credits_balance -= cost
    tx = CreditTransaction(
        user_id=user.id,
        amount=-cost,
        transaction_type="DEDUCTION",
        description=f"发起【{plan_code}】高精度市场模拟计算 (-{cost} 积分)"
    )
    db.add(tx)
    db.commit()
    db.refresh(user)

    return {"deducted": cost, "remaining_credits": user.credits_balance}

def recharge_credits(db: Session, user: User, amount: int, payment_ref: str = "") -> User:
    """
    Recharges user credit balance.
    """
    user.credits_balance += amount
    tx = CreditTransaction(
        user_id=user.id,
        amount=amount,
        transaction_type="RECHARGE",
        description=f"充值积分 (+{amount} 积分) [订单号: {payment_ref}]"
    )
    db.add(tx)
    db.commit()
    db.refresh(user)
    return user
