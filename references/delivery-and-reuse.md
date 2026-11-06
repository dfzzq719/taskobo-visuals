# 独立交付与认可素材复用

独立资产、总览和认可记录分别管理。用户要求一幅插图与四个图标时，应交付五个不同的实际文件；总览不能替代它们。文件验收通过不代表业务含义、画风、视觉质量或用户认可已通过。

## 按生成任务验收文件

在产物目录建立`delivery-files.json`。文件路径相对于这份JSON，不能越出其目录树；明确声明每项的任务ID、文件形式与独立角色。

```json
{
  "schema": "taskobo-visuals.delivery-files/v1",
  "assets": [
    {"id": "icon-01", "file": "actual/icon-01.png", "representation": "generated-raster", "role": "independent"}
  ]
}
```

上例只适用于`generation-jobs.json`中只有`icon-01`的任务；有其他任务时逐项列出，不能省略。原生SVG的形式声明为`editable-vector`。

```text
python scripts/delivery_manifest.py --jobs generation-jobs.json --files delivery-files.json --output delivery
python scripts/delivery_manifest.py --jobs generation-jobs.json --files delivery-files.json --output delivery-with-receipts --run-dir run
```

输出目录必须是新的或空目录。通过后保存原始字节的独立副本到`assets/ID.png`或`assets/ID.svg`，并写出`delivery-manifest.json`；不重新生图、不改色、不截取总览。拒绝缺项、额外项、重复ID、同一文件或改名后的相同字节、明确标为overview等非独立角色的内容。失败时只写诊断清单，不复制部分资产混作完整交付。

PNG调用现有`check_assets`检查实际编码、尺寸与Alpha；透明资产还必须有完全透明像素。完整不透明场景按任务中的背景选择验收。Pillow不可用时报告限制，不擅自安装。SVG以XML结构检查原生几何、viewBox、自包含引用和格式，拒绝嵌入位图冒充可编辑矢量；结构通过仍不能证明图形语义、画法或实际透明边缘正确。

`accepted: true`仅指独立文件覆盖、身份和格式通过，`status`仍是`generated-unreviewed`。机器不能可靠识别改名的总览是否只画了目标物；每个文件仍需实际看图。原始业务资料、本机绝对参考路径不默认进入交付清单。

指定`--run-dir`时，通过生产记录核对同一任务快照、任务ID、产物哈希和明确的生成尝试。没有生产记录时不编造运行证据；有生成回执也不等于用户认可。

## 明确认可后再收录

```text
python scripts/asset_catalog.py init --catalog approved-assets
python scripts/asset_catalog.py approve --catalog approved-assets --manifest delivery/delivery-manifest.json --asset-id icon-01 --semantic-id document-review-pending --reviewer "实际审阅者" --source "实际认可记录或会议依据" --aliases aliases.json
```

`approve`是独立的明确操作。实际查看文件后，记录真实审阅者和依据；不能因为机器验收通过就自动执行，也不能把合成测试中的fixture认可记录称为真实用户批准。审阅者字段是调用者的记录，不是身份认证或数字签名。

可选别名文件示例：`{"zh-CN":["文档待审"],"ja":["文書の確認待ち"],"en":["pending document review"]}`。别名应对应同一业务含义，不把待审与已批准混为近义词。

目录按项保存业务语义、别名、画法与版本、角色色板、公司规范版本、使用尺寸、实际文件哈希、独立交付来源和认可记录。只复制选中的已验收资产，不默认收录业务原文或整份工作目录。已存在的认可记录不静默覆盖。

目录批准采用本地单写入锁；另一个批准操作正在执行时明确报busy，稍后重新读取后再试。崩溃留下的锁需明确检查，不自动删锁或声称具备多用户服务权限。搜索读取完整的原子JSON快照。

## 搜索与原样复用

```text
python scripts/asset_catalog.py search --catalog approved-assets --query "確認待ち" --style-id monoline --style-version 2 --display-size 96px
python scripts/asset_catalog.py search --catalog approved-assets --query "pending" --palette palette.json --profile-version 1.0.0
python scripts/asset_catalog.py reuse --catalog approved-assets --id "搜索返回的准确ID" --output reuse/icon-01.png --style-id monoline --style-version 2 --display-size 96px
```

色板文件接受角色对象、`{"roles":...}`或`{"palette":{"roles":...}}`，必须包含`ink`和`primary`。比较完整角色色值，大小写归一化，不根据近似颜色自动匹配。使用尺寸是原先计划的显示框，不是PNG的原生分辨率。

搜索仅返回明确认可且满足所给过滤条件的资产，返回前重新核对实际文件哈希。中文、日文与英文来自明确的业务描述和别名，不做模糊翻译来替换业务状态。没有匹配项时返回空结果，不偷偷换样式、换配色或重新生成。

复用必须明确选中一个目录ID，并再次核对文件与适用条件。输出文件必须是新文件，保持原格式和原字节，不转描、不重渲染；新的布局与上下文仍需确认。目录是本地JSON与文件，不提供网页托管、多人权限、身份认证或服务端搜索。
