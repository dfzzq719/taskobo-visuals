# 本地制作记录与单项重做

`production_run.py`只记录宿主实际执行的工作，不调用生图、API或队列。输入是`prepare_visual_jobs.py`输出的`planned`任务，不能直接拿网页草稿冒充已准备任务。

## 建立与开始

```text
python scripts/production_run.py init --jobs generation-jobs.json --run-dir run-001 --max-attempts 3
python scripts/production_run.py start --run-dir run-001 --asset illustration-01
```

新运行目录不得覆盖旧目录。运行保存任务文件哈希、每项原始提示词、相对路径的参考图副本及其哈希。`start`只选中一个资产并保存尝试快照，不表示图片已经生成；如使用修订提示词，加`--prompt-file actual-prompt.txt`。宿主随后必须实际把返回的提示词和参考图交给可用工具。输出摘要不展开提示词正文。

## 记录真实输出或失败

宿主调用完成后，用其实际工具信息填写一份本地JSON；未知的模型、seed和请求ID保持`null`，不能推测或编造：

```json
{
  "schema": "taskobo-visuals.tool-receipt/v1",
  "tool": "imagegen",
  "outcome": "succeeded",
  "model": null,
  "seed": null,
  "hostRequestId": null
}
```

```text
python scripts/production_run.py record --run-dir run-001 --asset illustration-01 --attempt 1 --receipt tool-receipt.json --output actual-output.png
python scripts/production_run.py status --run-dir run-001
```

`record`读取真实存在的PNG、JPEG、WebP或SVG，将原始字节复制到该次尝试目录，记录输出、工具回执、提示词和参考的哈希。原图不被修改。结果为`generated-unreviewed`，不自动判为语义、审美、原生矢量或用户认可通过。文件头检查不替代`check_assets.py`、独立素材交付检查或实际看图。

失败时不能填写成功输出：

```text
python scripts/production_run.py fail --run-dir run-001 --asset illustration-01 --attempt 1 --error "实际工具报错或未返回图片"
python scripts/production_run.py start --run-dir run-001 --asset illustration-01 --retry
```

可为`fail`附带`--receipt`；该回执的`outcome`必须为`failed`。脚本不会自行重试。每个资产最多1至5次尝试，缺省3次；失败或要求修改的资产用`--retry`，已经生成的资产只有显式`--regenerate`才会开始下一次。其他资产及旧尝试的文件不被覆盖。达到上限时先复核问题，再决定另建运行，不隐性无限调用工具。

重做缺省沿用最近一次尝试的实际提示词和参考快照，不退回最初计划；提供新的`--prompt-file`才替换该次提示词。`record`中途退出但尚未写入结果时，只允许用完全相同的已保存回执／输出字节续记；不同字节明确拒绝。已经完成的结果不可覆写。开始尝试的快照先写入非编号暂存目录，全部完整后才发布编号目录；未完成的暂存记录不会被冒认成已开始或已生成。

## 检查与验收记录

```text
python scripts/production_run.py review --run-dir run-001 --asset illustration-01 --attempt 1 --decision changes-requested --reviewer agent --note "请记录实际发现的语义或视觉问题"
python scripts/production_run.py review --run-dir run-001 --asset illustration-01 --attempt 1 --decision passed --reviewer human --note "只有实际发生人工检查时才这样记录"
```

检查事件追加保存，旧结论不被覆盖。`passed`显示为`reviewed`，`changes-requested`可驱动单项重做；它们记录调用者提供的检查结论，不认证检查者身份，也不等于今后全部输出获用户认可。没看过图时不写通过。

本地回执可以交给独立素材交付检查：`delivery_evidence(run_dir, asset_id, sha256)`只有在唯一尝试的资产ID、实际输出哈希和已保存字节均匹配时返回`runId/assetId/attempt/runReceiptSha256/jobsSha256`。交付程序还应比较任务文件哈希，避免把另一批内容或配色的输出挂到本批任务名下。重复使用同一输出而出现多个匹配尝试时报告歧义，不猜测应采用哪次。

## 范围与恢复

记录均在授权的本地运行目录，不默认发布任务正文或上传私人文档。哈希用于发现修改，不是管理员签名或服务商认证。不要手工改写`run.json`、尝试快照或输出文件；需要更改主题、共享画法或参考计划时另建任务和运行。运行期间的短锁阻止并发覆盖；异常退出留下`.production.lock`时，先核对是否仍有活动写入，再按实际情况处理，不自动删除正在使用的锁。
