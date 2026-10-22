# 企业叙事插画 / Enterprise Narrative

标识：`enterprise-narrative`。基础方向：`editorial`。2026-10-22，用户认可下图的画风并要求保留为一种能力；它是可选预设，不是所有业务必须采用的唯一风格。

![用户认可的企业叙事插画参考](../assets/approved/enterprise-narrative.png)

[机器可读预设](../assets/approved/enterprise-narrative.json)。参考来自本项目原创宣传图的用户反馈版本；保留其原始像素，不把截图中的图标当成已经拆分好的素材。

## 识别特征

- **成熟而亲和的人物**：接近真实成人的比例，面部做适度插画概括。表情和姿态自然、专业，人物围绕具体业务动作互动。
- **有层次的墨线**：外轮廓清楚，内部结构线更细、更轻；衣褶、发丝、设备结构有选择地交代，线条流畅，不用等粗黑线勾满所有细节。
- **色面与轻绘画感并用**：以克制的平涂和浅色块建立形体，叠加柔和明暗与轻微水彩、纸面质感。保留清晰轮廓，避免模糊的脏灰、塑料高光或过度写实的摄影感。
- **可信的工作情境**：对象比例、接合、透视和人物视线合理。环境细节用于解释工作，工具、台面、书籍等有明确用途。
- **温和、有秩序的商业气质**：明亮浅底、明确视觉重心、舒展留白。画面可有温度，但不采用幼态大头、夸张肢体或泛化的办公卡通。

参考图使用暖白、深蓝轮廓、蓝灰色面和少量焦点色。没有其他要求时可沿用这个方向；用户可改为公司色、文档配色或其他主题色。保持明暗层次和颜色角色，不把整张图简单染成同一种颜色。肤色等对象固有色按内容保留。

## 画风与构图分开

参考图的“多场景相框拼贴＋底部图标”适合宣传总览，但它是布局选项，不是本画风的定义。

- 说明一个业务动作：用一个完整场景，突出人物、对象和动作关系。
- 同一报告的系列插图：逐张保持线条、细节密度和人物处理一致，题材随内容改变。
- 展示服务适用面：可用数个场景拼贴，白色留边、轻微倾角与浅阴影形成层次；重叠不遮挡关键人物和对象。
- PPT或书籍：按正文位置预留空间，关键标题与说明尽量放在可编辑排版层。没有需求时不加品牌标题、相框或图标横排。

风格适用于各行业。参考中的制造、零售、医疗、教育只是题材示例，不自动进入新任务；同样也不自动加入车辆、芯片、医生或机器人。

## 复用方式

简报可写为：

```json
{
  "direction": {
    "id": "editorial",
    "preset": "enterprise-narrative",
    "origin": "user",
    "status": "draft"
  }
}
```

把参考图提供给生成工具时，先查看它，并明确其角色为**画风参考**。当前业务内容、配色和布局分别提供；不将参考图当成必须保留对象的编辑目标。工具只支持文字提示时使用下面的描述，并说明参考约束精度有限。

```text
Create an enterprise narrative illustration of [current subject and business action].
Mature, approachable adult figures with credible proportions and purposeful gestures.
Elegant graded dark-ink contours, fine selected structural detail, restrained flat
color shapes, soft tonal modeling and a subtle watercolor-on-paper finish.
Believable objects, shallow natural perspective and a bright, spacious composition.
Use the supplied image for drawing treatment only; subject, layout and palette come
from the current brief. Palette roles: [current roles]. Composition: [current layout].
Avoid childish proportions, exaggerated limbs, generic office clipart, glossy plastic
3D and decorative futuristic effects. Do not copy the reference's industry objects,
frame collage, branding or icon row unless the current request calls for them.
```

## 同系列图标与交付

主题图标可用 `precision` 的描边填色方法，与主插图保持轮廓、色系和视觉重量上的亲缘。小图标减少纹理与人物细节，保证实际显示尺寸下清楚。需要可编辑SVG时另行制作真实矢量几何；生成式位图只交付为位图，不以追摹、换扩展名或嵌入图片代替原生SVG。

成图检查成熟人物、自然动作、可信结构、墨线层次、清爽色面及目标尺寸上的辨识度。色系替换后仍应看出同一套画法；构图应服务本次信息。已认可参考用于约束方向，不能承诺不同模型或多次生成像素一致。新产物仍需按本次任务检查。
