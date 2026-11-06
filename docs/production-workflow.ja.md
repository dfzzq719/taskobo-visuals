# 生成を記録し、採用した素材を引き継ぐ

[制作ツール](https://taskobo.com/free-tools/taskobo-visuals/tool/) · [社内基準と草稿の準備](enterprise-standard.ja.md) · [検証範囲](validation-matrix.ja.md)

Webで条件を整え、Skillを導入したAIで実際に制作する。生成後は、どの条件で何ができたかをローカルに記録する。修正対象だけを再制作し、採用した原図は次の資料でもそのまま使える。

以下は、準備済みの `generation-jobs.json` に `icon-01` だけが含まれる例。複数素材の場合は、すべてのIDを納品一覧に含める。コマンドはローカルの記録・確認を行い、画像モデルや外部APIを呼び出さない。原図、記録と中間ファイルは、現在のプロジェクトで許可された出力先に保存する。

## 1. 制作の条件を固定して記録を始める

```sh
python scripts/production_run.py init --jobs generation-jobs.json --run-dir run --max-attempts 2
python scripts/production_run.py start --run-dir run --asset icon-01
```

`init` は新しい記録フォルダーを作る。`start` は試行を開始し、実際に渡す提示詞と参照見本の保存場所を返す。画像はまだ生成されていない。表示された条件を確認し、利用中のAIの画像生成機能で制作する。

試行回数の上限は素材ごとに1〜5回で指定できる。例の `2` は初回と再試行を合わせた上限だ。参考図や色を後から変更した場合、既存の試行を変更済みの条件で実行したことにしない。

## 2. 実際の生成結果を結び付ける

画像ツールから実際に成功応答と原図を受け取った場合だけ、応答の記録を作る。取得できない値は `null` のまま残す。

```json
{
  "schema": "taskobo-visuals.tool-receipt/v1",
  "tool": "imagegen",
  "outcome": "succeeded",
  "model": null,
  "seed": null,
  "hostRequestId": null
}
```

この例を `tool-receipt.json` に保存し、実際の出力ファイルを指定する。

```sh
python scripts/production_run.py record --run-dir run --asset icon-01 --attempt 1 --receipt tool-receipt.json --output actual/icon-01.png
python scripts/production_run.py status --run-dir run
```

生成済みの状態は `generated-unreviewed`。原図が保存できたことと、意味・画風・人物の動作が正しいことは別に確認する。モデル名やseedを受け取っていない場合、使ったと推測して記録しない。ツール応答の記録は提供元による署名や実行証明ではない。

## 3. 必要な素材だけを修正する

実際の表示サイズと明暗の背景で原図を確認し、必要に応じて `check_assets.py` の診断を利用する。意味と画法を目視で確認し、結果を明示的に記録する。

```sh
python scripts/production_run.py review --run-dir run --asset icon-01 --attempt 1 --decision changes-requested --reviewer agent --note "説明対象が小さく見えるため、細部を減らす"
python scripts/production_run.py start --run-dir run --asset icon-01 --retry --prompt-file revised-prompt.txt
```

`--retry` は失敗または修正要求のある素材に使う。新しい試行にも、実際の生成結果と確認を記録する。`record` と `review` の `--attempt` には、`start` が返した新しい試行番号を使う。修正しなくてよい素材はそのまま保持する。

完了済みの素材を別案として再制作するときは `--regenerate` を明示する。応答が不明な場合は、既存の出力を調べてから再実行する。すでに生成されていた画像を見落として重複生成しない。

生成に失敗したと確認できた場合は `fail` に理由を残す。`review --reviewer agent` はAgentによる目視確認の記録であり、ユーザーの承認を意味しない。

## 4. 個別の納品物を確認する

`delivery-files.json` で、予定した素材IDと独立ファイルを対応させる。`file` はこのJSONからの相対パスで、その配下のファイルだけを指定する。

```json
{
  "schema": "taskobo-visuals.delivery-files/v1",
  "assets": [
    {
      "id": "icon-01",
      "file": "actual/icon-01.png",
      "representation": "generated-raster",
      "role": "independent"
    }
  ]
}
```

```sh
python scripts/delivery_manifest.py --jobs generation-jobs.json --files delivery-files.json --output delivery --run-dir run
```

出力先は新しいフォルダー、または空のフォルダーを使う。納品用フォルダーには、独立素材と `delivery-manifest.json` が入る。一覧画像を個別素材の代わりに数えず、IDの不足・余分なID・同じ画像の重複納品などを検出する。生成ビットマップを、図形を編集できるSVGと呼ばない。 SVGでは自己完結した図形の構造を確認する。見た目の透明度、空の図になっていないか、外形や画法は目視で確かめる。

この検査の `accepted: true` はファイルと納品範囲の確認結果で、視覚品質や業務内容の採用を意味しない。実画像の内容と同じ画法かどうかは別に確認する。

## 5. 採用した原図を再利用する

内容、画法、権利と用途を確認して採用した素材だけを、明示的にカタログへ追加する。

```sh
python scripts/asset_catalog.py init --catalog catalog
python scripts/asset_catalog.py approve --catalog catalog --manifest delivery/delivery-manifest.json --asset-id icon-01 --semantic-id document-review-pending --reviewer reviewer-name --source "内容と画法を確認して採用"
python scripts/asset_catalog.py search --catalog catalog --query document-review-pending --style-id technical-spot --style-version 1 --display-size 96px
python scripts/asset_catalog.py reuse --catalog catalog --id ENTRY_ID --output reused-icon.png
```

例の `technical-spot` と画法版は、実際の生成タスクに合わせる。`ENTRY_ID` は検索で返ったIDに置き換える。`--palette` や `--profile-version` も指定し、今回の配色や社内基準に合う候補へ絞れる。配色の絞り込みは記録した色の役割を比較し、画像の全画素がそのHEXに一致するという意味ではない。表示サイズは配置先での大きさで、原画像の解像度とは区別する。

再利用はファイルを照合した上での原図コピー。作り直さず同じ素材を使える。意味や今回の用途が異なる場合はそのまま転用しない。採用記録は明示的な判断の記録であり、本人確認や社内承認システムを代替するものではない。

記録の管理、生成の実行、目視確認、ユーザーの承認を区別する。新たな生成や公開は、現在の依頼で許可された範囲に従う。
