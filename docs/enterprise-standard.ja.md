# 社内基準を保存し、制作へ引き継ぐ

[README](../README.md) · [制作ツール](https://taskobo.com/free-tools/taskobo-visuals/tool/) · [生成と検証範囲](validation-matrix.ja.md)

## 1. インストールを確かめる

```sh
python scripts/doctor.py --expected-version 0.5.2
python scripts/doctor.py --skills-root /path/to/installed-skills
```

版、画法一覧、参照ファイルとハッシュ、補助プログラムを確認する。同名Skillの検出には明示したディレクトリだけを調べる。診断は別のインストールを移動・削除しない。既定のJSON出力にはローカルパスを含めない。

## 2. Webの草稿に意味を補う

Webではテーマ、具体的な画法、色、外形、用途と表示サイズを選ぶ。現在選べる画法は[制作ツールの画風欄](https://taskobo.com/free-tools/taskobo-visuals/tool/)で確認する。出力は `status: draft` の制作意向だ。Skillを導入したAIに渡し、本資料の意味、描く対象・動作、必要な出典と誤示を補う。

```sh
python scripts/prepare_visual_jobs.py --brief draft.json --validate-only
python scripts/prepare_visual_jobs.py --brief completed.json --normalize-ready --output ready.json
python scripts/prepare_visual_jobs.py --brief ready.json --output jobs.json
```

欠けた項目の検出は終了コード2で返す。意味を補わないまま草稿を生成タスクにしない。`--normalize-ready` は完全な意味計画だけを明示的にreadyへ移し、文書を理解したり内容を創作したりしない。旧版の完全なAgent作成ブリーフは引き続き利用できる。出力の `planned` はまだ画像がない状態で、ホストAIの画像生成機能で実際に制作する。

## 3. 社内基準を共有する

制作ツールでは基準JSONをローカルに読み込み、差異を確認してから適用する。固定した画法と色を黙って置き換えない。CLIではチェックサム付きの可搬ZIPを使える。

```sh
python scripts/company_profile.py validate --profile company.json
python scripts/company_profile.py export --profile company.json --output company-standard.zip
python scripts/company_profile.py import --archive company-standard.zip --output new-standard-folder
python scripts/prepare_visual_jobs.py --brief ready.json --profile company-standard.zip --output jobs.json
```

[規格例](../assets/company-profile.example.json)はデモ規格で、実企業の承認済み基準ではない。名前、規格版、1つの画法IDと画法版、配色・固定項目、字体、必要な採用見本を保存する。参照画像は相対パスとハッシュで持ち、ZIPでは実際の画像を検証する。Webは画像ファイルのハッシュ照合や画像生成を実行しないため、その確認はインストール先のSkillで行う。未知・廃止・版違い・固定色の衝突はエラーにし、適用しなかった規格を適用済みと呼ばない。

中国語はMicrosoft YaHei、日本語はMeiryo UI。指定フォントで文字を配置できる環境で確認する。画像生成だけで厳密な字体一致を保証せず、文字と数値が重要な画像では制御可能な文字層を使う。会社が分配するのは規格と採用素材であり、生成モデルの全画素の一致を約束するものではない。

## 4. 実画像を検査する

```sh
python scripts/check_assets.py --input illustration.png --input icon.png --output inspection --display-size 96 --background '#EDF3FF'
python scripts/check_assets.py --input presentation-image.png --output page-inspection --opaque
```

Pillowを利用できる環境が必要。原画像は変更しない。Alpha、サイズ、主体の範囲、余白や端の裁切リスク、明暗と文書色の合成見本を出力する。リスク表示は画像を見る手掛かりで、意味・画風・自然な外形・美観を自動承認したものではない。完全なページ画像では不透明背景を明示する。

## 5. 生成記録と採用素材を引き継ぐ

素材ごとの試行、実際の原図、確認結果をローカルで記録する。失敗・修正対象だけの再制作、独立ファイルの納品確認、採用した原図のカタログ登録と再利用は、[制作・納品・再利用の手順](production-workflow.ja.md)を参照する。ファイル検査の合格と、内容・画風の採用判定は分ける。

## テスト

```sh
python -B -m unittest discover -s tests -v
node tests/web-contract.cjs
```

標準ライブラリの契約テストと、Pillowがある環境の画像診断テストを分けて実行する。NodeがなければWeb相互運用テストは省略を明示する。CIはPython・画像診断・Nodeの契約を検査し、画像生成や審美評価は実行しない。画像証拠は[検証範囲](validation-matrix.ja.md)に別記する。
