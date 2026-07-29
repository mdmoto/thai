# 临时人工收款码资源

生产页面只读取以下三张固定图片，不生成动态支付链接，也不接收自动回调：

- `apps/web/public/payments/alipay-qr.png`：支付宝收款码，用于 STARTER、GROWTH、SCALE。
- `apps/web/public/payments/wechat-pay-qr.png`：微信收款码，用于 STARTER、GROWTH、SCALE。
- `apps/web/public/payments/wechat-appreciation-qr.png`：微信赞赏码，仅用于 ฿990 的 BASIC_DECISION_SINGLE。

任一图片缺失时，付款页会禁用“我已付款”按钮，并提示客户联系官方客服，避免误付。
