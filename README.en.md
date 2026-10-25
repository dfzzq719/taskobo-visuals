# Taskobo Visuals

Each style applies the exact same drawing method to illustrations and icons under one style ID. Composition and detail adapt to size; contours, fills, materials, texture and lighting do not switch to a related style. One shared registry controls changes and retirement for both asset kinds. Existing examples do not establish pair validation for every style.

Enterprise illustrations and coordinated thematic icons, made with your own AI from a topic or document. Content, art direction and palette remain independent choices.

[日本語](README.md) · [中文](README.zh-CN.md) · [Showcase](https://taskobo.com/free-tools/taskobo-visuals/) · [Request workspace](https://taskobo.com/free-tools/taskobo-visuals/tool/) · [Download v0.3.7](https://github.com/dfzzq719/taskobo-visuals/releases/tag/v0.3.7)

![Original promotional example combining icons, an illustration and Japanese copy](examples/service-story/page-02.png)

[Explore the three-image story: icons and text → icons, illustration and text → illustration and text](examples/service-story/README.ja.md). These original images were generated using one `enterprise-narrative` drawing method and palette. Original PNGs, prompts and generation records are included. The Web workspace prepares requests; creation takes place in your AI with the Skill installed.

## Compare visual directions

[Browse 23 icon drawing and material examples](docs/icon-styles.ja.md), controlled for business themes and blue/navy palette. These are selection examples, not measured adoption rankings or 23 fixed presets.

The Skill has three starting directions: `precision`, `editorial` and `dimensional`. Two named optional presets are documented: [`technical-spot`](references/technical-spot.md) and [`enterprise-narrative`](references/enterprise-narrative.md). Choose content, palette and viewpoint independently.

v0.3.5 also bundles [23 drawing recipes](references/style-recipes.json), selectable by number or name and combined with the current document's subjects and palette. Both comparison boards have been regenerated from these recipes and reviewed cell by cell. [Document-to-image validation](docs/document-driven-validation.ja.md) records three fictional inputs and 12 actually generated Technical Spot icons. The comparison boards cover all23 styles on controlled topics; document-driven forward generation currently covers No.06, not every style or arbitrary input.

## Start

1. Extract the Skill ZIP from [v0.3.7](https://github.com/dfzzq719/taskobo-visuals/releases/tag/v0.3.7) into a Skill directory supported by your AI application. The folder is `taskobo-visuals`; repository-based installers should use this repository root.
2. Reload the Skill and invoke `$taskobo-visuals` with a topic, use, palette and art direction. The Web workspace creates a reusable request and brief JSON.
3. Review at the intended size and share the approved master, palette and prompts with your team.

```text
Use $taskobo-visuals to make an illustration and six icons for a business handover document.
Use the same enterprise-narrative drawing method for both the illustration and icons.
Use cobalt #1456D9 and navy #0D2046; the target document has a light background.
Generate standalone artwork on genuinely transparent backgrounds, with restrained
semi-transparent shadows if needed. No display platforms or backing plates.
Supply native SVG only for separately constructed editable geometry, plus transparent PNGs.
Save the brief, usage notes and generation prompts.
```

Independent icons and illustrations default to genuine Alpha transparency. Explicit full-scene or comparison-board backgrounds take precedence. [Open the current compact Technical Spot reference](assets/presets/technical-spot-compact.png). v0.3.6 bundles this generation reference and records actual display size, detail level and a style lock. Small icons use one primary object and at most one necessary cue. The older two-view board remains a historical viewpoint study, not the default small-icon anchor.

Standalone artwork defaults to a natural unframed silhouette, with optional peripheral Alpha fading or an explicitly opaque full scene. [Framing](references/image-framing.md) controls composition and background independently of the shared drawing style; it does not add a separate illustration style.

## What runs where

- **Web:** browse samples, recolor their SVG previews, create requests and brief JSON locally in the browser.
- **Your AI with the Skill:** read document evidence, plan imagery and use available image/file/vector tools.
- **Downloads:** four fictional industry packs, each with a raster illustration, six separately authored SVG icons, transparent PNG exports, palette and prompts.

Your AI must supply image generation and any file/vector tools. No model, API key, hosted generation backend, Web document upload or automatic Word/PPT insertion is bundled. Preview color changes do not recolor downloaded packs. Generated pixels and composition vary; approve series masters rather than promising identical output across models.

The Skill's maintained instructions are Chinese; the default public README, usage guide and sample explanations are Japanese. Specify your desired output language.

See [industry samples](docs/gallery.ja.md), [document extraction and usage](docs/guide.ja.md), [development and compatibility](docs/development.ja.md), [the Skill](SKILL.md) and [MIT license](LICENSE). [Taskobo Diagrams](https://github.com/dfzzq719/taskobo-diagrams) covers structured business diagrams.
