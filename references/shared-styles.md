# 插图与图标的统一样式

用户于2026-10-25明确要求：插图与图标使用完全相同的画法，一一对应；修改、停用或删除样式时同时生效，不分开管理。

## 一份定义

[style-recipes.json](style-recipes.json)是当前唯一生效的画法目录。每条记录的同一个 `id`、`treatment`、`styleReference`、`styleVersion` 和 `status` 同时用于 `illustration` 与 `icon`。两种资产的画法不能只保持“相近”或“亲缘”；选择企业叙事画法时，配套图标也保留它的墨线、色面和轻水彩处理，不能自动换成 Technical Spot。

23个既有作例的编号保持不变。`enterprise-narrative` 是已有命名预设，作为未编号条目纳入同一目录，不增设或重排已发布图标编号。旧 `icon-style-recipes.json` 保留为v0.3.6历史快照，当前生成入口不读取它，也不继续维护第二套画法。预设说明和认可记录是说明/来源，不是独立的图标样式配置。

大小可以影响构图、对象数量和细节量，不能改变轮廓、填色、材质、纹理与光照方法。完整场景与独立透明图形可以有不同背景，但不能据此变成另一画法。主题和色系仍按本次文档或用户要求确定。

## 一个选择

```json
{
  "direction": {"styleId": "enterprise-narrative"},
  "palette": {"roles": {"ink": "#0D2046", "primary": "#1456D9"}},
  "assets": [
    {"id": "handover-scene", "kind": "illustration", "meaning": "两人核对交接内容", "subject": "两名同事共同查看交接清单", "displaySize": "PPT半页", "composition": "以共享清单和交接动作形成重心", "background": "transparent"},
    {"id": "handover-icon", "kind": "icon", "meaning": "交接核对", "subject": "一张清单与一个核对提示", "iconSizePx": 96, "background": "transparent"}
  ]
}
```

`direction.styleId`是统一入口；历史 `direction.recipe` 的编号/名称和 `direction.preset` 仍可解析，但同时出现时必须指向同一条记录。`direction.id`仍可记录旧基础分类，不能作为两种资产的不同画法。不要新增 `illustrationStyle`、`iconStyle` 或资产级 `direction/styleId` 覆盖。

运行 `python scripts/prepare_visual_jobs.py --brief brief.json --output generation-jobs.json` 为两种资产编排任务。兼容入口 `prepare_icon_jobs.py` 只接受图标，但共用同一套实现和目录。两者都不生成图片；宿主应实际传入任务中的参考图，生成并检查后才能称为成图。

## 一个生命周期

- 新增：在统一目录增加一条双用途记录；已有编号不复用。分别记录两类作例的验证状态。
- 修改：只改共享画法记录，递增其 `styleVersion`，检查两类输出；不维护图标专用的另一份画法。
- 停用：将同一条记录的 `status` 置为 `retired`，两类任务均拒绝使用，不静默换风格。
- 删除：从当前目录移除同一条记录；未知ID不回退。历史原图、提示词、固定发行包和既有生成记录不随目录修改被删除。

支持两种资产不等于已经验证了两种成图。`validation`分别记录已有证据，尚未制作的配套图不能标成已完成；这是验证记录，不是第二套样式。当前规则统一画法管理，不能承诺不同模型生成相同像素。
