# Linker 网关契约规则

## 网关请求

每次真实网关请求必须记录：

- 请求方法
- 请求 URL
- 请求头
- 业务明文请求体
- 加密请求体结构
- 脱敏后的签名生成输入
- timestamp 和 nonce

常见请求头：

- `Content-Type: application/json`
- `X-Linker-AppId`
- `X-Linker-Timestamp`
- `X-Linker-Nonce`
- `X-Linker-Signature`

## 鉴权与加密

分别校验：

- appId 存在且与 appSecret 匹配
- 应用已绑定目标商家
- timestamp 被网关接受
- nonce 符合当前防重放策略
- SM3 签名被接受
- SM2/SM4 请求加密被接受
- 加密响应可由测试侧独立解密

## 业务成功判定

业务成功必须同时满足适用条件：

- 收到网关 HTTP 响应
- 原始响应契约有效
- 响应解密成功
- 解密后的业务 `code` 表示成功
- `data` 结构符合接口契约
- 返回记录符合请求筛选条件和权限范围
- 场景要求数据对账时，对账通过

HTTP 200、存在 encryptedData 或响应可解密，都不能单独代表业务成功。

## 异常用例

适用时覆盖：

- 缺少 `X-Linker-AppId`
- appId 错误
- appSecret 或签名错误
- 缺少 timestamp
- timestamp 过期
- nonce 重复或重放
- encryptedData 格式错误
- algorithm 错误
- 未授权店铺、商家或资源
- 缺少业务必填参数
- 业务参数格式非法
- 互斥参数同时传入
