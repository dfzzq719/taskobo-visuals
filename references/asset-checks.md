# 安装自检与实际成图检查

这些脚本只读输入，不联网、不安装依赖，也不自动移动或删除旧版Skill。生成任务准备仍可只用Python标准库；PNG检查需要当前环境已有Pillow。图形检查不能代替业务含义、人物动作和画风的看图判断。

## 安装与版本

```text
python scripts/doctor.py --expected-version 0.5.2
python scripts/doctor.py --expected-version 0.5.2 --skills-root /explicit/installed-skills
```

检查Skill版本、统一样式目录、两类资产支持、参考图文件及哈希、辅助脚本语法与导入。只在明确给出`--skills-root`时扫描该目录下一层；按`SKILL.md`中的名称识别同名备份，不因目录名写了backup就忽略它。发现重复或版本不符时停止按该安装继续制作，由Agent核对正确安装；自检本身不替用户修改配置。

默认JSON省略本机绝对路径、脚本异常堆栈与源文档内容。私下排查需要定位安装目录时可加`--include-paths`，这份结果不默认进入公开素材包。可选的Pillow、PDF依赖未安装会说明能力边界；工具不会擅自安装它们。

## 独立透明素材

```text
python scripts/check_assets.py --input icon.png --output /authorized/output/icon-qa --display-size 96 --background "#EDF3FF"
python scripts/check_assets.py --input scene.png --output /authorized/output/scene-qa --display-size 640x360 --background "#F4F5F7"
```

`--input`可重复指定。`--output`必须明确指向用户授权的产物目录，报告和诊断预览都不写回输入。输出不能覆盖任何输入文件。脚本验证实际PNG编码、原文件哈希、像素尺寸、Alpha通道及极值、可见主体范围、透明留白、边缘像素。带透明索引的调色板PNG也按实际Alpha检查，不仅根据扩展名判断。

诊断预览保持完整原图的长宽比及透明留白，在指定的实际使用框内显示。面板从左到右为浅底、深底，以及明确传入的文档底色；各面板的位置与色值写在JSON里，不把文字烘焙进预览。预览只做缩放与Alpha合成，不修图、不替换背景、不改变原文件。

对于背景铺满的场景、封面或整页宣传图片，加`--opaque`；此时不要求透明，也不把画面铺到边缘当作裁切风险。全透明空图仍属于错误。

## 解释结果

- `passed`仅表示文件检查没有阻断项。`status`始终为`generated-unreviewed`，语义、画风和视觉审阅明确记为`not-performed`。
- 缺Alpha、意外全不透明、全透明空图或无法读取的文件属于阻断项，退出码为2。
- 留白较多、明显像素接触边缘属于风险提醒，需在实际使用尺寸看图判断；有意的偏置构图可能合理。
- 边缘仅有很淡的半透明像素会单独提醒，可能来自柔和阴影或渐隐，不能据此断言阴影被裁切。
- 白边、语义误示、人体结构、精确字体与同系列画法一致性不由这些像素检查自动批准。

发现影响理解的问题后，只针对原因修订，再重复同一目标检查；没有新问题时不不断扩大生成范围。

## 维护者回归检查

```text
python -B -m unittest discover -s tests -v
```

仓库中的GitHub Actions分别运行标准库路径和提供Pillow的PNG路径。测试验证输入不被修改、真实Alpha与尺寸、边缘风险分级、预览合成、同名安装、参考哈希和失败退出状态。脚本测试通过不等于所有画法的图片已经实生成或通过视觉验收。
