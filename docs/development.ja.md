# 開発・互換性

[公開README](../README.md) · [利用ガイド](guide.ja.md) · [変更履歴と固定配布](https://github.com/dfzzq719/taskobo-visuals/releases)

## 生成元と文書の言語

Skill手順と内容の維持基準は中国語。公開README、利用ガイド、業種別説明、画風の見本は日本語。英語の概要も用意する。画像内の製品名は付けず、名称と説明は変更できる本文に置く。

`examples/*/generation.prompt.txt` は各業種例の画像生成リクエスト、`request.ja.txt` は再利用する短い依頼文、`provenance.json` は生成元と範囲を記録する。新しい画風作例と透過PNGの生成プロンプトは `docs/assets/icon-styles/` に保存する。これらの見本は内蔵imagegenによるオリジナルのビットマップ。

表示用比較表には読みやすい共通の背景を設ける。独立素材の透明背景とは区別する。元の比較表やプリセット参考画像を上書きせず、新しい表示画像を別ファイルに保存する。

## Webのビルド

PythonとPillowを使う。

```bash
python -m pip install Pillow
python tools/build_site.py --output site
```

作品展示、制作ツール、4業種の計6ページを作る。Taskoboのポータル共通CSSとブランド素材を使うため、taskobo.com内への配備を想定する。業種のリンクから制作ツールに進むと、許可したサンプルIDに応じてテーマと配色を入力する。

生成ファイルとSkill ZIPは内容のハッシュを含む名前で配布する。公開済みの固定ZIPは書き換えない。Skillの生成規則を修正するときは新しい版で配布し、過去の固定ZIPと表示画像の履歴を保持する。

## ローカルの文書抽出

Python 3.10以上が必要。

```bash
python scripts/extract_context.py --input proposal.pptx > document-context.json
```

PPTX、DOCX、Markdown、テキストの証拠を読取り専用で抽出する。PDF文字抽出には追加の `pypdf` が必要。画像だけの文書には利用中のAIのOCR機能を使う。抽出器自体はテーマを決めず、Agentがページ・段落の根拠を読んで提案する。

## 名称と既存リンク

現在の名称はTaskobo Visuals、Skill名とフォルダー名は `taskobo-visuals`、呼出しは `$taskobo-visuals`。以前のTaskobo Illustrationから改名した。

- 元のGitHubリポジトリの識別子と履歴を引き継ぐ。
- 既存の `taskobo-illustration.*` JSON schema識別子は互換性のため保持する。
- 旧WebページURL、および展示ページの `#request` と `#install` は現在のページ・制作ツールへ誘導する。
- 元の参考画像、過去の生成リクエスト、公開済みの固定アーカイブは履歴として保持する。

## 表現と素材の確認

SVGは独立した図形として作り、PNGを埋めただけのものを編集可能なベクターと扱わない。透明PNGのAlpha、明暗両方の背景での輪郭、小サイズでの意味、権利と業務上の内容を確認する。シリーズの承認済み見本は版付きで保存する。
