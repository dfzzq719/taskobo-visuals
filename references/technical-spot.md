# 技术主题小插图 / Technical Spot Illustration

标识：`technical-spot`。基础方向：`precision`。用户于2026-10-25要求保留参考中的画法，状态为 `accepted-option`。新生成样稿仍为 `draft`，不能视为用户逐张认可的母样。

![当前紧凑画法参考：少量对象、清楚轮廓、平面色块](../assets/presets/technical-spot-compact.png)

[机器可读预设](../assets/presets/technical-spot.json) 的 `generationReference` 是当前生成用参考；查看该图并把它传给图像工具，仅借鉴画法及细节密度，不复用它的业务对象和颜色。当前参考仍为待用户逐图认可的原创草稿。早期[双视角研究样稿](../assets/presets/technical-spot.png)保留作历史视角研究，不能据其较多设备细节决定小图标的默认密度。用户原始参考仅作私有画法参考，不纳入公开包。

独立输出默认透明背景，平视和浅轴测相同。当前紧凑参考具有真实Alpha；早期双视角样稿的白底只用于研究，不继承为输出底色。内置 imagegen 使用 `transparent_background: true`，交付前检查真实Alpha和深浅底上的边缘。

## 识别特征与适用范围

用户已明确：这是二维的平面说明插画。明暗仅辅助识别结构，不建立球面、枕状体积、塑料材质、倒角或挤出厚度。对照图默认正面；人头是平面圆形，衣服是平面色块。浅轴测仅指二维绘制的投影视角，不转为3D材质渲染。

- **分级轮廓**：示例用深蓝灰外轮廓，内部结构线更细、更轻。曲线和接合流畅，稍有插画亲和感，但不画成抖动草线。
- **克制色面**：主题色与浅灰、中性面交代对象，以少量平面明度差说明结构；不依赖强渐变、玻璃高光或照片纹理。
- **具体而简化的物件**：比例、接合和重叠可信，保留用于识别用途的结构。细节介于符号和完整业务场景之间，通常围绕一个对象或一个小关系。
- **清楚的说明性气质**：适合企业PPT、报告、培训资料中的能力、设备、服务和业务动作。它不是工程结构图或精确操作证明。

基础 `precision` 强调简洁符号与描边填色；本预设可保留更多物件结构和轻微插画感。`enterprise-narrative` 更适合人物、业务动作与环境构成的完整情境，并使用轻绘画质感。这些是不同画法；同一系列的插图与图标共同选择一个样式ID，不按资产类型混搭。选择本预设时两者都使用二维描边填色，尺寸只影响细节量，不改变平面画法。

## 按实际尺寸控制密度

- **compact（小图标默认）**：约72–128px，一个清楚主对象＋至多一个必要辅助提示；主轮廓和大色面优先。移除密集电路、鳍片、成排接口和无助于辨认的机械纹理。专业性来自准确取舍，不来自零件数量。
- **standard（较大的说明插图）**：显示空间足够时才保留更多结构和一两个必要关系，仍有一个视觉重心。若关系本身复杂，改用更大的结构图，不把它挤成图标。
- **24/32px**：另作符号简化，不能承诺这套说明插图直接缩小仍可读。

“汽车”“AI”“感知”等文档主题决定当前含义，不自动要求画出完整设备总成。若需要表达多项能力，选择一个能辨认的代表物件，文字承载其他组成项。色板、透明度和无底座通过，仍不等于复杂度与风格已通过。

## 视角与配色独立选择

| 维度 | 可选值 | 选择依据 |
|---|---|---|
| 视角 `viewpoint` | `front`、`side`、`three-quarter`、`shallow-isometric` | 让本次对象最易辨认的面；不要把侧视图也称为等距图。 |
| 底座 `base` | `none` | 本预设不加装饰展示台、方形承托或底板，浅轴测也不例外。 |
| 配色 | 用户色、公司色、文档色或推荐色板 | 深色轮廓、主色、浅色面、中性面的角色保持清楚。蓝灰只是示范，不是固定品牌色。 |

同一交付系列统一主要视角、轮廓层级和细节密度。比较视角时可像样稿一样分行标示；普通业务系列不无理由混用。物件自身具有语义的结构仍按内容保留，不额外铺设承托整个图标的装饰底板。用户以后明确要求重新设计时，以新要求为准。

题材来自当次任务。车辆、卫星、地球和机械臂只是用户参考中的内容，不成为本预设的默认对象；同样适用于金融、零售、物流、医疗、教育、能源及专业服务。

## 复用方式

```json
{
  "direction": {"id": "precision", "preset": "technical-spot", "origin": "user", "status": "draft"},
  "layout": {"viewpoint": "front", "base": "none"}
}
```

使用图像工具前查看当前紧凑参考，并作为style reference实际传入。记录版本、配方、参考图哈希、`detailLevel`、`iconSizePx`和色板；当前对象、业务动作、视角分别确定，不把样稿当成必须保留对象的编辑目标。`detailLevel`缺省按实际尺寸选择，小图标默认compact。

```text
Create a technical spot illustration of [current object and business action].
Use graded dark contours, finer lighter structural lines, restrained flat fills,
flat color regions, minimal graphic tonal accents and credible simplified proportions.
Use a 2D line-and-fill illustration, never a shaded 3D render. No spherical lighting,
puffy volume, plastic shine, bevels, extrusion, ambient occlusion or cast shadow.
Human head circles and torso fills remain flat; viewpoint does not imply 3D material.
Keep a smooth, steady, mildly illustrative contour. For a compact icon, use one dominant
object plus at most one supporting cue, broad readable flat fills and very few internal
lines. Remove dense circuitry, cooling fins, repeated ports, screws and device clusters.
Do not increase detail merely because the subject is technical. Match the CURRENT compact
reference's density at the actual display size. Viewpoint: [front / side / three-quarter / shallow-isometric].
No decorative display base, pedestal, square support platform or backing plate,
including in shallow-isometric views. Palette roles: [current user or organization roles].
Export isolated artwork on a genuinely transparent background with an Alpha channel.
Keep any required soft shadow semi-transparent and fading to zero opacity; no white matte.
Use the reference for drawing treatment only. Subject, layout and palette come from
the current brief. Avoid photorealistic texture, glossy plastic, heavy gradients,
decorative scenery and copying objects from the reference.
```

生成后按实际显示尺寸看轮廓、结构、明暗和语义；小尺寸不清楚就减细节。位图保留为位图，需要编辑结构时另制原生SVG。保存本次提示词与检查记录；生成方向可复用，像素和结构准确性仍需逐图确认。
