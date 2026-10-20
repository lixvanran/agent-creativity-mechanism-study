# 路线 B v2 · 冒烟日志

- 时间：2026-10-21 01:33:17 → 2026-10-21 01:36:45
- 模型：MiniMax-M3.1-Flash-Preview ｜ 端点：https://api.minimaxi.com/v1（被测侧**不走 OpenRouter**）
- **调用数：14 / 上限 20**（成功 12）｜ 端到端耗时 232 s
- 黑名单自检：PASS ｜ 状态可分性对照：PASS ｜ 代理自测：PASS ｜ 告警自测：PASS

## 调用清单（每行 = 一次真实 HTTP 调用）

| # | purpose | model | max_tokens | finish | 内容长度 | ok | 秒 |
|---:|---|---|---:|---|---:|:-:|---:|
| 1 | al_gen | MiniMax-M3.1-Flash-Preview | 8000 | stop | 254 | True | 84.8 |
| 2 | al_ex | MiniMax-M3.1-Flash-Preview | 1400 | stop | 225 | True | 9.6 |
| 3 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 16 | True | 2.5 |
| 4 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 15 | True | 1.7 |
| 5 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 17 | True | 3.0 |
| 6 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 17 | True | 3.2 |
| 7 | al_gen | MiniMax-M3.1-Flash-Preview | 8000 | stop | 393 | True | 31.5 |
| 8 | al_ex | MiniMax-M3.1-Flash-Preview | 1400 | length | 0 | False | 13.8 |
| 9 | al_ex | MiniMax-M3.1-Flash-Preview | 2000 | stop | 343 | True | 30.1 |
| 10 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 17 | True | 2.3 |
| 11 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 15 | True | 13.4 |
| 12 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | length | 0 | False | 11.1 |
| 13 | check2 | MiniMax-M3.1-Flash-Preview | 2000 | stop | 16 | True | 22.2 |
| 14 | check2 | MiniMax-M3.1-Flash-Preview | 1200 | stop | 16 | True | 2.9 |

## 状态可分性对照（离线，0 次调用）

```json
{
 "states": [
  "none",
  "unmentioned",
  "supported",
  "contradicted",
  "unverified"
 ],
 "L1_legacy_same_target_same_f7_13": {
  "unmentioned": true,
  "supported": true,
  "contradicted": true,
  "unverified": true
 },
 "L1_all_true": true,
 "L2_legacy_target_delta_per_op": {
  "EXTRACT": 0.0,
  "VERIFY": 0.0,
  "SPLIT": 0.0
 },
 "L2_delta_is_op_independent": true,
 "L2b_random_w_delta_per_op": {
  "EXTRACT": -1.708838,
  "VERIFY": -1.708838,
  "SPLIT": -1.708838
 },
 "L2b_delta_is_op_independent": true,
 "legacy_checkpoint_w_found": true,
 "L3a_legacy_relative_order_of_target_ops_by_state": {
  "unverified": [
   2,
   0,
   1
  ],
  "unmentioned": [
   2,
   0,
   1
  ],
  "supported": [
   2,
   0,
   1
  ],
  "contradicted": [
   2,
   0,
   1
  ]
 },
 "L3a_order_is_state_invariant": true,
 "L3b_legacy_score_vectors_identical_3verdict_states": true,
 "L3c_legacy_argmax_by_state": {
  "unverified": "GEN_PLAIN",
  "unmentioned": "GEN_PLAIN",
  "supported": "GEN_PLAIN",
  "contradicted": "GEN_PLAIN"
 },
 "L4_legacy_argmax_unchanged_by_global_feature": true,
 "V1_v2_rows_differing_per_state": {
  "none": 5,
  "unmentioned": 5,
  "supported": 5,
  "contradicted": 5,
  "unverified": 5
 },
 "V1_v2_4states_not_all_identical": true,
 "V1_v2_unmentioned_vs_supported_differ": true,
 "V2_witness_argmax_by_state": {
  "none": "VERIFY",
  "unmentioned": "SPLIT",
  "supported": "GEN_PLAIN",
  "contradicted": "GEN_PLAIN",
  "unverified": "VERIFY"
 },
 "V2_witness_argmax_varies": true,
 "L6_legacy_candidate_sets_by_state": {
  "none": [
   "EXTRACT",
   "GEN_ANGLE",
   "GEN_PLAIN",
   "SPLIT",
   "STOP",
   "VERIFY"
  ],
  "unmentioned": [
   "EXTRACT",
   "GEN_ANGLE",
   "GEN_PLAIN",
   "SPLIT",
   "STOP"
  ],
  "supported": [
   "EXTRACT",
   "GEN_ANGLE",
   "GEN_PLAIN",
   "STOP"
  ],
  "contradicted": [
   "EXTRACT",
   "GEN_ANGLE",
   "GEN_PLAIN",
   "STOP"
  ],
  "unverified": [
   "EXTRACT",
   "GEN_ANGLE",
   "GEN_PLAIN",
   "SPLIT",
   "STOP",
   "VERIFY"
  ]
 },
 "L6_split_unavailable_when_supported": true,
 "L6_verify_unavailable_when_supported": true,
 "feature_dim_v2": 30,
 "feature_names_len": 30
}
```

## 代理自测（离线）

```json
{
 "w_hat_A": 0.5,
 "w_hat_B_repeat": 0.5,
 "w_hat_C_floral": 0.5,
 "w_hat_D_new_anchored": 1.0,
 "w_hat_E_with_conflict": 1.0,
 "repeat_does_not_increase": true,
 "floral_does_not_increase": true,
 "new_anchored_increases": true,
 "conflict_does_not_increase": true,
 "conflict_rate_E": 0.2,
 "terminal_reward_example": 3.0,
 "all_pass": true
}
```

## 告警变异自测（离线）

```json
{
 "collapse_fires": true,
 "op_entropy_fires": true,
 "op_coverage_fires": true,
 "weight_frozen_fires": true,
 "reward_stall_fires": true,
 "conflict_fires": true,
 "closure_fires": true,
 "tau_increases_when_collapsed": true,
 "all_pass": true
}
```
