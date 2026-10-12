---
name: skill-catalog-entry
description: このリポジトリのLIFEスキル一覧に、新規または更新したスキルの紹介カードと解説ページを追加・同期する。
---

# スキル解説ページの追加

対象は `Kyoto_Univ/index.html` のスキルタブと `Kyoto_Univ/ui/skills/` の解説ページ。定義元は `Kyoto_Univ/skill_catalog.py`、画面の雛形は `Kyoto_Univ/ui/portal.html` と `shell.html`。生成済みHTMLを直接編集しない。

1. 対象のSKILL.mdと、説明に必要な参照・スクリプトを読む。受付可能な依頼例、入力、出力、実際の制約を確認する。存在しないCLIやフラグを作らない。
2. `skill_catalog.py` のSKILLSに1件追加（更新なら同じidを編集）。既存の項目に合わせ、id、title（日本語）、icon（shell.htmlで定義済みのsymbol）、path（リポジトリ相対のSKILL.md）、overview、commands、commandNote、flow、details、files、limitを記載する。idはfrontmatterのnameと一致させ、重複させない。
3. `INTRO_DETAILS` に同じidの補足を追加する。カードの概要は短く、詳細は解説ページに置く。flowの種別はdet（規則処理）、tool（ツール）、llm（読解・生成）、human（本当に必要なユーザー確認）から実装に合うものを選ぶ。承認手順を勝手に追加しない。
4. `python3 Kyoto_Univ/update_portal.py` を実行。カードと `ui/skills/<id>.html` が生成される。スキル定義自体の新規作成・更新が必要ならskill-creatorを使う。
5. 定義と紹介が一致すること、カードから解説ページに開けること、コマンド一覧・構造図・詳細・定義元が表示されること、戻るリンクとメニューが動くことを確認。画面確認ではPCとスマートフォン幅で横にはみ出さないことも確認する。

生成処理はpathが存在しない項目を省略し、frontmatterのnameとidが違う場合はエラーにする。ファイルの存在と名前の整合を先に確認する。
