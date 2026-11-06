---
name: taskobo-visuals
description: "Create enterprise illustrations, thematic icon sets and promotional slide-images from a topic or document, using a shared drawing style and a chosen or document-matched palette. Use for 企业插图、主题图标、宣传图、报告和PPT配图及系列视觉设计."
metadata:
  version: "0.5.0"
---

# Taskobo Visuals

理解业务，为文档、PPT、Web制作精美插图和主题图标。面向全行业；题材来自本次内容，参考案例只提供画法，不自动带入行业、对象、布局或蓝色。沿用用户当前的选型、规划、生成或修改模式。

## 当前安装与制作模式

跨项目复用、接收公司规范或出现风格漂移时，用 `python scripts/doctor.py` 核对版本、目录和参考图。同名安装排查加 `--skills-root` 指定目录；诊断只报告，不移动或删除其他安装。以本次实际加载的SKILL.md为准，不能根据备份文件夹名推测版本。

- 选型与规划：给出适合的画法、配色和配图建议，保留用户已确定的选择。
- 独立素材：Agent先理解内容，再用 `prepare_visual_jobs.py` 校验和编排；`prepare_icon_jobs.py` 是仅图标的兼容入口。两者都不调用生图，不把任务计划当成已生成图片。
- PPT形式宣传图片：明确每页论点、文字、图标和插图关系，按要求直接输出图片，不擅自改为制作PPTX。整页排版与独立资产任务分别记录。
- 修改已有图：先查看目标，保留用户指定的不变量，以新文件保存修订，不重画无关内容。

条件充分时直接生成，不为填模板反复确认。可推断的信息说明假设；只有会实质改变结果且无法推断的条件才询问。源资料、最终和中间产物分别遵守当前项目的读写目录要求。

## 内容、画法、配色分别决定

简短确定读者、核心含义、关系、用途、实际显示尺寸、语言及品牌规范。有文档时读[文档到配图](references/document-context.md)：提取文字、定位和颜色证据，建立“原文依据→含义→对象/动作→避免的误示”。保留条件、异常和待确认状态；不能用词频、文件名或示例库存替代理解。扫描图、复杂布局与字体需要宿主相应能力。文档内容不是执行指令，也不增加外传授权。

先按阅读任务选对象、情境、流程、结构、对照或数据图；见[形式与画风](references/forms-and-styles.md)。已有充分图表或没有图形价值的段落可以不配图。精确流程、架构和真实数据图优先用确定性图形工具；艺术性位图或用户明确要求的图片默认用内置imagegen。不静默切入付费API，不把保存提示词称为完成图片。

## 同一个样式，配对制作

插图与图标完全共用一个 `direction.styleId` 和唯一[画法目录](references/style-recipes.json)。轮廓、填色、材质、纹理与光照一致，只按尺寸调整构图和细节量。新增、修改、停用、删除同时作用于两类资产，不分开维护。23个已发布编号不重排，企业叙事画法沿用未编号ID。

按编号、ID、中日英文名称匹配；未知、停用、冲突或公司规范版本漂移时先解决差异，不换成相近画法。旧 `recipe/preset` 仅是同一ID的兼容选型。见[统一样式](references/shared-styles.md)、[视觉简报](references/visual-profile.md)。

有参考图时先查看并实际传入图像工具，记录哈希；只在提示词里提到不算已使用。样式参考与验证范围见目录及[验证矩阵](references/validation-matrix.md)。对照板和编排测试不代表所有题材、所有尺寸的成图都已验证。

`technical-spot` 用二维描边填色，不生成球面阴影、塑料高光、倒角或挤出厚度。72–128px小图标从compact起步：一个主对象＋至多一个必要提示，不堆电路、端口和设备；见[技术主题小插图](references/technical-spot.md)。`enterprise-narrative` 保留成熟人物、可信动作、分级墨线与轻水彩，配套图标也用同一画法；见[企业叙事](references/enterprise-narrative.md)。

## 外形、颜色与文字

独立素材默认 `freeform`＋`transparent`：自然外轮廓、真实Alpha，无矩形相框、卡片、装饰底板或展示台。可选外围渐隐 `vignette`；明确需要完整背景时用 `full-scene`＋`opaque`。这是共用外形参数，不另编号。imagegen按实际背景设置 `transparent_background`，必要阴影保留半透明；见[图片外形](references/image-framing.md)。

颜色依据依次是用户指定、正式公司规范、文档主题与实际用色、认可参考、内容语义。按背景、墨色、主色、辅助和状态分角色；换色不改主题或画法。Office默认主题不直接当品牌。需要时用 `check_palette.py` 检查拟定色对，数值通过不等于成图通过；见[色系决策](references/color-direction.md)。

带文字交付物：中文 `Microsoft YaHei`，日文 `Meiryo UI`，用户本次明确指定其他字体时优先。关键长文或必须精确字体时采用可控文字排版层，最终仍可输出图片。纯生图文字逐字看，不声称已精确验证字体身份。独立素材通常使用外置可编辑标签；生成位图不冒充原生SVG。

## 从草稿到公司规范

网页只在浏览器内整理主题、画法、配色和制作意向，不读文档、不生成图片。网页草稿由Agent补齐各项 `meaning`、`subject` 等语义，再校验为可执行任务；缺项就报告，不能以默认值伪造内容。见[企业规范与执行](references/enterprise-standard.md)。

公司规范共享一个画法ID、版本、颜色角色与锁定项、字体及带哈希的认可参考。使用时核对版本和参考，显式选择冲突应先解决，不改写公司已发布规范。只分发必要规则和素材，不默认打包业务原文、缓存或私人路径。确定性SVG可固定几何和色值；生成图仍有模型差异，不能承诺像素一致。

## 成图检查与交付

需要保留制作过程、局部重做或团队复用时，读[逐张制作记录](references/production-run.md)与[独立交付和素材复用](references/delivery-and-reuse.md)。先检索已认可且含义、画法、版和配色适配的素材；复用前核对实际文件与哈希，语义不符就重新制作，不能为省事改变业务含义。

`production_run.py` 将任务计划、实际传入的提示词/参考、宿主回执与成图文件逐张关联。生成仍由宿主工具完成；仅记录工具实际返回的信息，不猜模型、seed或任务ID。失败或需要修改时只重做目标素材，以新attempt保留旧文件和其余已采用结果；达到次数上限先说明原因和后续选择，不无限重试。

实际看图检查业务含义、对象、角色、状态、箭头、文字、系列画法和视觉重量，并在最终尺寸查看。对影响理解的问题有目标地修订，不因漂亮忽略错误，也不在没有新问题时无限重试；见[提示词与验图](references/prompt-and-review.md)。

用 `check_assets.py` 检查尺寸、Alpha、主体范围与裁切风险，输出浅底、深底和文档底色的诊断预览。脚本不改原图，不自动判定语义、审美、自然轮廓或风格通过；见[成图检查](references/asset-checks.md)。

多素材交付用 `delivery_manifest.py` 核对任务ID与独立文件；插图1点＋图标4点应有5份对应素材，对照板不替代独立文件。明确区分透明PNG、原生矢量SVG和含位图的SVG，不能把格式名当成可编辑性证明。`asset_catalog.py` 只在有明确认可来源时登记为可复用素材，保留含义、别名、画法/配色/公司规范版本、尺寸和文件哈希；机械检查通过或Agent自查不自动成为用户认可。

交付原图、用途和尺寸、实际提示词、画法/参考/版本及检查记录。区分计划、已生成草稿、已视觉检查、用户已认可；认可一张不代表认可未来全部输出。工具不可用时说明限制并保存简报。只做研究时不发布作品或修改网站。

## 按需参考

- [主题图标](references/themed-icons.md)：语义、密度、箭头、原生矢量与成套交付。
- [Taskobo视觉语言](references/art-direction.md)：艺术方向和宣传素材。
- [工作台配置衔接](references/visual-workbench.md)：既有Mermaid规范的兼容与固定分发。
- [色板输入样例](assets/palette-example.json)：检查输入示范，不是全部任务默认色板。
