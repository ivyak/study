# Gitフック

このリポジトリでは、PDFをローカルに保持し、Gitの管理対象から外します。
`.gitignore`が通常の追加を防ぎ、`pre-commit`がステージされたPDFの追加・変更を拒否します。
PDFの削除を記録するコミットは許可します。PDFの実ファイルは削除しません。

各クローンで、リポジトリのルートから次の設定を一度実行します。

```sh
git config --local core.hooksPath .githooks
```

実行にはPython 3が必要です。設定は他のPCへのクローンでは引き継がれません。
`git commit --no-verify`などでフックを回避できるため、誤操作の予防用です。
