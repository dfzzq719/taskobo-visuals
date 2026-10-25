# 统一视觉简报

成套插图、图标共用一个样式ID和同一画法，不设置独立的 `illustrationStyle`、`iconStyle` 或资产级画风覆盖。当前规则见[统一样式管理](shared-styles.md)。

成套插图、图标和服务交接应有一份可读的简报，字段可按任务取舍。下列是 v0.2 的建议契约，不冒充现有网页 API。

```json
{
  "schema": "taskobo-illustration.visual-brief/v1",
  "topic": {"title": "客户服务协作", "origin": "user", "evidence": []},
  "direction": {"styleId": "enterprise-narrative", "id": "editorial", "preset": "enterprise-narrative", "origin": "user", "status": "draft"},
  "palette": {
    "mode": "custom",
    "roles": {"paper": "#FCFBF8", "ink": "#0D2046", "primary": "#1456D9", "primarySoft": "#EDF3FF"},
    "lockedRoles": ["primary"]
  },
  "medium": {"kind": "presentation", "background": "light", "targetSize": "16:9"},
  "assets": [
    {"id": "visual-01", "kind": "illustration", "framing": "freeform", "background": "transparent", "purpose": "说明从咨询到交接的主要关系", "sourceRefs": ["slide:3"], "status": "planned"},
    {"id": "icon-01", "kind": "icon", "framing": "freeform", "background": "transparent", "purpose": "辨认人工确认", "sourceRefs": ["slide:5"], "status": "planned"}
  ]
}
```

`origin` 区分用户选择、文档依据和 Agent 建议；`status` 区分建议、草稿与已认可母样。只有确实读取过资料时才写 `sourceRefs`；示例中的页码不是任何真实文档的依据。

`medium.background` 记录放置素材的文档或页面底色；`assets[].background` 记录独立生成文件的背景，两者分别处理。新简报的独立图标和配图缺省为 `transparent`，保留真实 Alpha 和必要的半透明阴影；不可把 `palette.roles.paper` 或 `medium.background: light` 当成必须烘焙的底色。旧简报没有资产背景字段时沿用这一默认，用户明确指定完整场景或对照板背景时优先执行。

`assets[].framing`独立于画法：`freeform`是自然轮廓无外框、`vignette`是外围渐隐，两者要求透明背景；`full-scene`是明确要求的完整不透明场景。省略时按素材背景推断，不改动已有明确背景。详细规则见[图片外形](image-framing.md)。

`direction.styleId` 是当前统一样式标识；`direction.recipe/preset` 是历史兼容选型，必须解析到同一ID。`direction.id` 只作基础分类，不能给另一类资产分配另一画法。`direction.preset` 是可选的具体画风标识。`enterprise-narrative` 调用已认可的企业叙事插画参考；不提供该字段的已有简报仍按基础方向处理。认可参考图的画风，不等于新生成的每张图已获认可，所以新产物的 `status` 仍从草稿开始。题材写入 `topic`，相框拼贴或单场景等布局按任务另记，不能塞入画风标识或据此锁死配色。

技术主题小插图可写为下列片段。`technical-spot` 的基础方向为 `precision`；视角记录在 `layout.viewpoint` 中，和画法、主题、配色分别决定。视角可选 `front`、`side`、`three-quarter`、`shallow-isometric`，缺省为 `front`。本预设的 `layout.base` 固定为 `none`：浅轴测也不加装饰展示台、方形承托或底板。预设画法已作为可选能力保留，不代表原创样稿或本次产物已获认可。

```json
{
  "direction": {"id": "precision", "preset": "technical-spot", "origin": "user", "status": "draft"},
  "layout": {"viewpoint": "front", "base": "none"}
}
```

完整说明见 [技术主题小插图](technical-spot.md)。上述是可读简报的可选字段，不改变已有 schema 标识，也不表示所有旧网页已实现这些控件。

色系模式：`preset` 使用候选色板、`custom` 使用用户色值、`document` 从文档形成待核对建议、`organization` 使用公司已发布版本。用户明确锁定的颜色优先。图表工作台旧 `roles/settings` 通过原衔接说明读取，不擅自重命名原字段或声称旧工具已支持新契约。

发布素材时补充实际输出文件、提示词/生成源、尺寸、透明度与检查记录。业务原文和本地绝对路径不默认打入公共素材包。公司统一分发的是视觉规范与审核素材；位图生成仍需逐图检查，不能以模型参数固定为由承诺像素一致。

跨项目复用时记录 `styleLock`：Skill版本、配方ID、参考图相对路径及哈希、视角、配色和每个资产的 `iconSizePx`/`detailLevel`。`iconSizePx`是实际显示尺寸，不是导出分辨率。06号在约72–128px默认compact；`subjectParts`可显式列出主对象和必要辅助提示，compact最多两项，超出时先重新设计语义代表物。生成任务中的 `referenceImages` 路径相对于Skill目录，使用前查看并解析为本机路径传给图像工具。仅加载了规则、仅配色相同或仅PPT结构检查通过，均不等于视觉风格检验通过。
