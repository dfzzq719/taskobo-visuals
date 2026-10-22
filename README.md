# Taskobo Illustration

Enterprise illustrations and coordinated thematic icons, created from a topic or a document with your own AI. Content, art direction and palette remain independent choices.

[日本語の展示ページ](https://taskobo.com/free-tools/taskobo-illustration/) · [日本語の利用ガイド](docs/guide.ja.md) · [業種別ギャラリー](docs/gallery.ja.md) · [Releases](https://github.com/dfzzq719/taskobo-illustration/releases)

![Original cross-industry Taskobo Illustration portfolio](examples/portfolio.png)

## What it provides

- A reusable AI Skill with enterprise art direction, semantic icon planning and palette guidance.
- Local, read-only extraction of PPTX, DOCX, Markdown and text evidence; optional PDF text extraction with `pypdf`.
- Four fictional industry samples: manufacturing and logistics, retail and service, healthcare and care, education and training.
- Each sample includes an original AI-generated illustration, six native editable SVG icons, transparent PNG exports and reusable prompts.
- Japanese static showcase source, including actual SVG palette previews and a browser-local request brief builder.

The Skill instructions are currently written in Chinese. The usage guide, sample explanations and requests are Japanese. Specify the output language in your request.

## Install and use

Download the Skill ZIP from [Releases](https://github.com/dfzzq719/taskobo-illustration/releases) or the [showcase](https://taskobo.com/free-tools/taskobo-illustration/#install). Extract the `taskobo-illustration` folder into a Skill directory supported by your AI application and reload the session. The Skill lives at the repository root; install from this root if your application's repository installer supports it.

```text
Use $taskobo-illustration to make an enterprise illustration and a set of six icons
about employee onboarding for an internal training deck.
Keep the content topic, art direction and palette separate.
Use cobalt #1456D9 with navy outlines and an ivory ground.
Provide Japanese explanations, independent editable SVG icons and transparent PNGs.
Save the visual brief, source files and generation prompts.
```

Your AI application must supply image generation for raster illustrations, and local file/vector tools for editable SVG assets. The Skill does not bundle a model, an API key, a hosted generation service or automatic Word/PPT placement. Exact generated composition and pixels vary; review and approve series masters when consistency matters.

For the optional document extractor, Python 3.10+ is required:

```bash
python scripts/extract_context.py --input your-document.pptx > document-context.json
```

This command extracts evidence, not a topic prediction. The host Agent reads that evidence and proposes content, art direction and color. PDF text additionally requires `pypdf`; image-only documents require OCR supplied by the host.

## Samples and source

| Industry | Original files | Live sample |
| --- | --- | --- |
| Manufacturing and logistics | [Files](examples/manufacturing-logistics/) | [View](https://taskobo.com/free-tools/taskobo-illustration/samples/manufacturing-logistics/) |
| Retail and service | [Files](examples/retail-service/) | [View](https://taskobo.com/free-tools/taskobo-illustration/samples/retail-service/) |
| Healthcare and care | [Files](examples/healthcare-care/) | [View](https://taskobo.com/free-tools/taskobo-illustration/samples/healthcare-care/) |
| Education and training | [Files](examples/education-training/) | [View](https://taskobo.com/free-tools/taskobo-illustration/samples/education-training/) |

All sample scenarios are fictional. They do not represent customer deployments, measured outcomes, verified work instructions or medical advice. Generated illustrations are raster artwork; the SVG icons are separately authored geometry with no embedded bitmap. Palette changes in the web preview affect the inline SVGs only; downloadable sample files retain their documented original colors.

`generation.prompt.txt` records the exact built-in image generation request in each sample folder. `request.ja.txt` is the shorter reusable user request. `provenance.json` records origin and scope. The existing `assets/style-atlas.png` is an exploratory style comparison, not a set of approved brand masters.

The static website builder uses Python and Pillow:

```bash
python -m pip install Pillow
python tools/build_site.py --output site
```

It creates five pages for `/free-tools/taskobo-illustration/` and its sample routes. The portal shell shares the Taskobo root stylesheet and brand assets. It is intended for deployment within taskobo.com, rather than as a standalone root-level app.

## Related

[Taskobo Diagrams](https://github.com/dfzzq719/taskobo-diagrams) handles structured, editable business diagrams. This Skill handles enterprise illustration and thematic icon art direction. Use each for its task.

## License

[MIT](LICENSE), including the original sample assets provided here. No client documents or client project assets are included. The Taskobo name and logo identify the project; this license does not grant rights to imply endorsement.
