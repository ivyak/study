"""Build the local skill catalog from repository skill definitions and curated guides."""
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

SKILLS = [
    {
        'id': 'university-stem-study', 'title': '大学理系学習', 'icon': 'cap',
        'path': '.codex/skills/university-stem-study/SKILL.md',
        'overview': '講義資料・教科書・板書を基準に、理解から問題演習までを支えます。1周目の理解ガイド、復習用の参照資料、武器一覧、解法体系を役割ごとに整理し、実際に解いた結果から更新します。',
        'commands': [
            ('$university-stem-study この講義資料の1周目理解ガイドを作って', '科目・対象資料・範囲を指定。原典の順番に沿った短い補助解説を作成します。'),
            ('$university-stem-study この範囲の2周目用参照資料を作って', '学習済みの範囲を指定。定義・条件・公式・誤用しやすい点をまとめます。'),
            ('$university-stem-study この科目の武器一覧と解法体系を更新して', '原典と既存の資料を指定。問題の特徴と使える道具、条件・分岐を結びつけます。'),
            ('$university-stem-study 次に解く既存問題を選んで', '過去問・演習と学習進捗を指定。選定理由を添え、通常は解答を先に見せません。'),
            ('$university-stem-study この途中式で詰まった理由を調べて資料に反映して', '問題・自分の解答・詰まった場所を指定。必要な学習資料を補強します。'),
        ],
        'commandNote': 'Codexへの依頼例です。専用のCLIや固定フラグはなく、自然言語で対象と作りたい資料を伝えます。',
        'flow': [('tool', '原典・既存資料を取得', 'ファイル列挙、PDFの文字抽出、ページ画像の取得。'), ('llm', '原典と出題を読解', '定義・条件・理解の深さ・問題との対応を判断。'), ('llm', 'ガイド・武器・解法を作成', '学習段階に合わせて説明と問題選定を行う。'), ('tool', '資料を保存・参照先を確認', 'ファイル書き込みやリンクの存在確認。'), ('llm', '解答を分析して補強', '失敗の原因を分類し、既存資料へ統合。')],
        'details': [
            ('原典と重要度の根拠', '内容の正しさは担当教員の資料を基準にします。何を重点的に学ぶかは同じ教員・科目の過去問、授業演習、指定教科書の問題の順に検討します。過去問の所在が未調査なら京大過去問検索を利用し、確認済みの結果は日時と未確認範囲を読んで再利用します。'),
            ('4種類の資料の使い分け', '1周目ガイドは原典の読解を助ける短い注釈です。2周目用の参照資料は理解済みの知識を復元するためのもの。武器一覧には使用条件・見分けるサイン・原典を、解法体系には問題タイプ・基本ルート・分岐・検算を整理します。'),
            ('演習と更新のループ', '既存問題を優先して選びます。解いた結果から、知識不足、条件の見落とし、武器の選択、分岐不足、計算ミスなどを区別します。質問への説明はその場で答えたうえで、再利用価値があればガイドの該当箇所に要点だけを統合します。'),
            ('保存するもの', '既存構成を優先します。指定がなければ科目のstudy/に01_first_pass_guide.md、02_reference.md、03_weapons.md、04_solution_system.md、05_practice_queue.md、06_question_log.mdを置きます。原典は原則編集しません。'),
        ],
        'files': [('SKILL.md', '目的、原典の優先順位、Phase 0〜6の学習手順。LLMが読む指示書。')],
        'limit': '専用の自動判定スクリプトはありません。理解度・重要度・数学的な妥当性の判定はLLMの作業であり、ファイル保存が成功しても内容の正しさを自動保証するものではありません。',
    },
    {
        'id': 'handwritten-lecture-explainer', 'title': '板書・手書き講義解説', 'icon': 'pen',
        'path': '.codex/skills/handwritten-lecture-explainer/SKILL.md',
        'overview': '板書画像や手書きノートを読み、授業回ごとのHTMLへ清書・解説します。微分積分学続論II程度の詳しさで内容を再構成し、mockの目次・要旨・節のUIを使います。元画像はページに表示しません。',
        'commands': [
            ('$handwritten-lecture-explainer この板書画像を第2回のHTMLにまとめて', '科目と授業回、画像を指定。画像の順序を確認し、内容を清書・補足します。'),
            ('$handwritten-lecture-explainer この手書きPDFの授業回を判定して解説して', '資料一覧なども確認し、判定の根拠と不確かな箇所を記録します。'),
            ('$handwritten-lecture-explainer 前回の解説と演習問題を踏まえて更新して', '既出用語と出題上の重要度を反映してHTMLを更新します。'),
        ],
        'commandNote': 'Codexへの自然言語の依頼例です。対象画像・PDFと科目、分かれば授業回を指定します。専用のCLIや固定フラグはありません。',
        'flow': [('tool', '画像・先行資料を確認', '原画像とOCRを照合し、読順、判読不能箇所、先行解説を調べる。'), ('llm', '授業回と章節を判定', '資料一覧と内容を照合し、確認済み・推定・不明を分ける。'), ('llm', '問題と用語を照合', '演習・過去問、既出の記号と前提を確認する。'), ('llm', '板書を清書・解説', '式、導出、例題、条件を補い、節・章・全体の読了時間を見積もる。'), ('tool', 'LIFEのHTMLを作成', '共通シェル、目次、要旨、章節を配置し、ポータルを更新する。')],
        'details': [
            ('画像の読み取りと対応付け', '全画像・全ページを確認し、向き、欠け、重複、板書の順番を見ます。OCRや文字抽出で疑わしい式は原画像へ戻って確認します。画像番号やノートのページ番号を授業回とは区別し、各節の原典位置と不明箇所を管理記録へ残します。'),
            ('読むための清書', '定義、仮定、重要な数式、導出、例題、検算を残し、初出の用語と必要な前提を説明します。原典にない補足と訂正は区別します。図は意味を文章で説明し、必要なら説明用の図を付けます。'),
            ('詳しさと読了時間', '問題本文があれば解法で使う箇所を詳しくします。問題がなければ内容上の必要性で暫定判断します。節・章・全体に、式や推論の負荷を含む概算の読了時間を付けます。'),
            ('LIFEでの表示', 'mock.htmlの開閉式目次、講義を通して言いたいこと、章と節を共通シェルに載せます。元の板書・ノート画像や空の画像欄は表示せず、本文だけで授業内容を追えるようにします。HTMLは科目フォルダ直下へ保存し、ポータルの該当回の「解説」へ登録します。'),
        ],
        'files': [('SKILL.md', '画像の判読、授業回判定、清書・解説、LIFEのHTML作成手順。'), ('agents/openai.yaml', '表示名、短い説明、初期プロンプト。'), ('study/handwritten-explanations/course-context.md', '実行時に科目内へ作る授業回の根拠・原典対応・用語の管理記録。')],
        'limit': '手書きの判読、授業回、内容の重要度、読了時間はLLMの判断です。読めない部分は推測で埋めず、確認範囲と影響を示します。',
    },
    {
        'id': 'lecture-slide-explainer', 'title': '講義スライド解説', 'icon': 'slide-icon',
        'path': '.codex/skills/lecture-slide-explainer/SKILL.md',
        'overview': '講義スライドPDFの全ページを確認し、要旨、章別目次、スライド1枚ごとの解説を作ります。LIFEの科目ページは共通の横タブを使い、mock.htmlと微分積分学続論IIの実ページに沿って、目次・言いたいこと・解説と原スライド画像を配置します。',
        'commands': [
            ('$lecture-slide-explainer このPDFをスライド1枚ずつ解説して', '対象PDFと科目を指定。要旨・章別目次・個別解説を作成します。'),
            ('$lecture-slide-explainer この資料の授業回と資料順を確認して', 'PDFと配布一覧やシラバスを指定。確認済み・推定・不明を根拠とともに記録します。'),
            ('$lecture-slide-explainer この演習問題に合わせて解説の詳しさを調整して', '既存解説と問題本文を指定。重点・標準・概要を判断します。'),
            ('$lecture-slide-explainer 前回の解説を踏まえて今回のPDFの解説を更新して', '先行解説と対象PDFを指定。用語の初出位置と参照を引き継ぎます。'),
        ],
        'commandNote': 'Codexへの自然言語の依頼例です。出力形式と保存先を指定できます。専用のCLIや固定フラグはありません。',
        'flow': [('tool', 'PDF・先行解説を取得', '文字抽出、原ページ画像の取得、既存記録の読み込み。'), ('llm', '資料の位置と構成を判定', '授業回・資料順・章分けに根拠と確認状態を付ける。'), ('llm', '問題・用語・前提を照合', '重点度、既出用語、必要な前提を判断。'), ('llm', '1枚ずつ解説・時間を見積もる', '意味・論理・用途を説明し、読解負荷も見積もる。'), ('tool', 'LIFE科目ページを作成', 'ui/shell.htmlの横タブを同期し、mock準拠の目次・要旨・解説と原画像を配置してポータルを更新。')],
        'details': [
            ('PDFページと授業回を区別する', '全ページを読み、図・数式・段組みが抽出結果だけで理解できない箇所は画像で確認します。PDFページ番号は1始まりで、印字されたスライド番号とは別に記録します。1ページに複数枚あれば位置も付け、内容が似ているだけで授業回を確定しません。'),
            ('要旨から個別解説へ', '資料を通して言いたいことを通常1〜3文で示し、原典の章構成を優先して目次を作ります。全スライドを元の順番で章と個別解説に対応させます。表紙・目次・参考文献も対応を残し、重複や段階表示では追加された点を短く説明します。'),
            ('詳しさと用語の管理', '確認できる問題本文をもとに重点・標準・概要を判断します。未出題だけで必要な前提を削りません。未説明の用語・記号は初出で短く補い、先行解説に説明済みのものは参照を使います。読順が不明なら説明済みと仮定しません。'),
            ('読了時間と保存先', '各枚・各章・資料全体に概算の読了時間を付けます。毎分400〜600字を暫定目安にし、式や図との照合・推論の負荷を加えます。LIFEでは横のタブをui/shell.htmlから同期し、ポータルと同じ項目・順序・アイコンにします。本文はmock.htmlと微分積分学続論IIの実ページを規範とし、開閉式目次、講義を通して言いたいこと、章見出し、各スライドの解説と対応する原画像をこの順・配置で作ります。解説と画像は各スライド単位で組にし、study-lesson・study-kind・study-createdを付けてポータルを更新します。course-context.mdは判定根拠と用語記録用で、読者向け本文の代用にしません。'),
        ],
        'files': [('SKILL.md', '資料判定、要旨・目次、個別解説、用語管理、時間見積もり、LIFE科目ページ作成の指示。'), ('agents/openai.yaml', 'スキル選択画面に使う表示名・説明・初期プロンプト。')],
        'limit': '専用の解析CLIはありません。授業回の同定、章分け、重要度、読了時間の負荷補正はLLMによる判断です。固定手順の指示があることと、スクリプトによる決定論的な判定は別です。',
    },
    {
        'id': 'kyoto-past-exams', 'title': '京大過去問検索', 'icon': 'scroll',
        'path': '.codex/skills/kyoto-past-exams/SKILL.md',
        'overview': '4データベースから資料を探し、ファイル名の教科・教員・年度を3条件で照合します。内容を4種類のバッジに分類し、ファイル名をタイトルとしてDriveリンクをまとめます。',
        'commands': [
            ('$kyoto-past-exams 工業数学A1・柴山・履修年度2026の資料リンクを探して', '教員名のファイル名表記を必ず指定します。未入力では検索しません。'),
            ("python3 .codex/skills/kyoto-past-exams/scripts/search.py collect --course '工業数学A1' --teacher '柴山' --out /tmp/exams.json", '4ソースの公開一覧を収集。資料自体は保存しません。'),
            ("python3 .codex/skills/kyoto-past-exams/scripts/search.py collect --course '工業数学A1' --teacher '柴山' --out /tmp/exams.json --resume", '未巡回の一覧を再開。進展がなければ未走査URLとして残します。'),
            ("python3 .codex/skills/kyoto-past-exams/scripts/search.py search --index /tmp/exams.json --course '工業数学A1' --teacher '柴山' --academic-year 2026", 'ファイル名だけから同名教科・教員・年度の3条件を照合します。'),
        ],
        'commandNote': 'Pythonコマンドはリポジトリのルートで実行します。--teacherは必須で、ファイル名の教員表記を指定します。教員名を省略した検索はできません。裏付けのある別名だけ--aliasを両コマンドに指定します。',
        'flow': [('tool', '4ソースの一覧を取得', '未巡回・取得失敗を記録し、上限の先は再開。'), ('det', 'ファイル名を3条件で照合', '同名教員の前年度、それ以前、違う教員名。'), ('llm', 'Driveプレビューで種類を確認', '問題・講義資料・解答・演習問題のバッジ。'), ('tool', 'リンク一覧へ統合', 'タイトル名・資料の種類・URLの3列。最後にパス付き未走査領域。')],
        'details': [
            ('ファイル名から判定する3条件', '同名教科・同名教員・前年度、同名教科・同名教員・前年度よりも前、同名教科・違う名前の教員だけを判定します。講義資料や解答でも、ファイル名が条件に合えば「あり」です。'),
            ('表記の一致と資料の種類を分ける', '教科・教員・年度はファイル名だけで判断し、フォルダや本文から補いません。正規化はNFKC・空白除去・大小文字統一。本文は種類の判定にだけ使い、複数種類は複数バッジ、未読やプレビュー不能は未確認です。'),
            ('資料を保存せずリンクする', 'Driveの閲覧・プレビューを利用し、PDFや画像はダウンロードしません。表示はファイル名のタイトル・資料の種類・URLのみ。取得日時、根拠、掲載元などは管理JSONに保存します。'),
            ('未発見と未走査を区別する', '進展があれば取得を再開します。未巡回・取得失敗・全件取得未確認を「なし」にせず、一番下にDrive上のパスとURLを記載します。配下を見られない場合は親フォルダだけを示し、同じDrive IDは1件にまとめます。'),
        ],
        'files': [('SKILL.md', 'ファイル名の3条件、種類のバッジ、リンクのみの出力手順。'), ('scripts/search.py', '公開一覧の取得とファイル名の照合。'), ('references/sources.md', '4ソースの入口と取得制約。')],
        'limit': '名前の表記一致は実際の同一人物の保証ではありません。ファイル名に教員・年度がない場合や公開一覧・プレビューが取得できない場合は未確認になります。',
    },
    {
        'id': 'explain', 'title': 'コード解説', 'icon': 'pen',
        'path': '.claude/skills/explain/SKILL.md',
        'overview': '実コードを読み、初学者がコードと答え合わせしながら読める解説資料を作ります。ファイル・行番号付きの引用、構造図、用語の説明、理解度チェックを含め、資料の更新時には現在のコードへ参照を合わせ直します。',
        'commands': [
            ('/explain -o docs/catch-up src/services/export.py', '対象ファイルと出力先を指定して解説を作成します。'),
            ('/explain -o docs/catch-up -n 14 --max-lines 250 workerの非同期処理', '連番と1ファイルの行数上限を指定。既定の上限は300行です。'),
            ('/explain -o docs/catch-up --single --level dev このPRの変更内容', '短いテーマを1ファイルにまとめ、開発者向けに説明します。既定の読者レベルはzeroです。'),
            ('/explain -o docs/catch-up --update 13_4 --no-quiz', '既存資料の引用・行番号を更新し、理解度チェックを省略します。'),
            ('bash .claude/skills/explain/scripts/check_docs.sh docs/catch-up --max-lines 300 --root /path/to/repo', '行数、相対リンク、コード引用の実在・行番号、目次からの導線を検算します。'),
        ],
        'commandNote': 'Claude側のスキルです。/explainは会話からの呼び出しで、シェルコマンドではありません。対象は自然言語でも指定可能。-o/--outが未指定なら保存先を確認し、分冊構成は本文作成前に提示して承認を得る手順です。',
        'flow': [('llm', '対象・保存先・構成を確認', '対象コードを読み、読者に合わせて分冊構成を設計。'), ('human', '分冊構成を承認', '本文作成前にファイル名・内容・目安時間を確認。'), ('llm', '実コードを引用して解説', '用語、図、理解度チェックを作成し、目次を更新。'), ('det', 'check_docs.shで検算', '行数・リンク・コード参照・目次を規則で検査。'), ('llm', '検算結果から修正', '参照や構成の問題を直して再検算。')],
        'details': [
            ('実コードを読む', '対象ファイルの全文と呼び出し元・先・型定義・テストを確認します。引用は実物のコピーを使い、リポジトリルートからの相対パスと行番号を添えます。古い設計書とコードが食い違う場合はコードを基準にし、死んだコードや仕様の罠も説明します。'),
            ('初学者が自力でたどれる説明', '型や関数の定義場所、言語の記法、標準ライブラリをその場で説明します。未経験者向けを既定にし、--level devなら比喩を減らして設計判断を中心にします。通常は末尾に3問の理解度チェックを付け、答えは折り畳み、対応する節へつなぎます。'),
            ('分冊と構成の確認', '通常は1ファイル200〜300行になるよう節を先に設計します。構成一覧を提示して承認後に本文を書きます。出力先に既存の資料があれば連番や体裁を合わせ、目次と前後ナビゲーションも更新します。出力先未指定時は書き始める前に確認します。'),
            ('検算と更新', 'check_docs.shで機械的に検査します。行数超過や目次導線の不足は警告、リンク切れや不正なコード引用はエラーとして扱います。検査は正規表現で拾える範囲に限られ、意味の正しさはLLMが確認します。--updateでは対象コミットまたは日付を更新し、引用と行番号を取り直します。'),
        ],
        'files': [('SKILL.md', '引数、出力先確認、構成承認、初学者向けの解説手順。'), ('references/page-template.md', '本文・ナビゲーション・理解度チェックのテンプレート。'), ('scripts/check_docs.sh', '解説資料の行数、リンク、引用、目次導線を検査。')],
        'limit': '検算スクリプトは解説の意味やすべてのリンク形式を検証しません。検査に通ることと、解説がコードを正しく説明していることは別です。',
    },
]

SKILLS.extend([
    {
        'id': 'goal-summary', 'title': '目標サマリ', 'icon': 'pen',
        'path': '.codex/skills/goal-summary/SKILL.md',
        'overview': 'Notionの最終目標テーブルと各目標の現状を読み、達成状況を短く整理します。日付付きのMarkdownを保存し、目標タブから履歴を読めるように更新します。',
        'commands': [('$goal-summary 現在の目標達成状況をまとめて', '指定Notionを取得して当日のサマリを保存します。'), ('python3 Kyoto_Univ/update_portal.py', '保存済みMarkdownを目標タブへ反映します。')],
        'commandNote': 'Codexへの依頼でNotion取得と要約を行います。再生成コマンドだけではNotionを取得しません。',
        'flow': [('tool', 'Notionの一覧と本文を取得', '対象ビューを最後まで読み、各目標のページを確認。'), ('llm', '現状を短く整理', '条件と現状を比較し、空欄や不明点を区別。'), ('tool', '日付付きMarkdownを保存', 'goal_managementに日本時間の当日分を保存。'), ('det', '目標タブを再生成', 'Markdownを日付の降順で表示。')],
        'details': [('根拠付きの現状把握', '名前・優先度だけでなく、各ページの目標・条件・現状を確認します。数値がなければ達成率を作らず、空欄は未確認とします。'), ('短いサマリと履歴', '全体の要約と目標ごとの短い表、根拠リンクを保存します。同日は更新し、過去日のサマリを残します。Notionへの書き戻しや計画の新規作成は対象に含めません。')],
        'files': [('SKILL.md', '対象Notion、判断基準、保存形式と更新手順。'), ('goal_management/YYYY-MM-DD.md', '日付ごとのサマリ。'), ('Kyoto_Univ/goal_reports.py', '短いMarkdownを安全なHTMLへ変換して一覧を作成。')],
        'limit': 'Notionにアクセスできる接続が必要です。達成状況の整理は記載内容に基づき、現実の達成を独立に確認するものではありません。',
    },
    {
        'id': 'skill-catalog-entry', 'title': 'スキル解説ページ追加', 'icon': 'scroll',
        'path': '.codex/skills/skill-catalog-entry/SKILL.md',
        'overview': 'スキル定義を読み、LIFEのスキル一覧に紹介カードと解説ページを追加・更新します。依頼例、処理の流れ、ファイル構成、制約を実際の定義に合わせて紹介します。',
        'commands': [('$skill-catalog-entry このスキルを解説ページに追加して', '対象SKILL.mdを指定して紹介を追加します。'), ('$skill-catalog-entry スキル定義の変更を解説ページに反映して', '既存紹介を現在の定義と同期します。'), ('python3 Kyoto_Univ/update_portal.py', 'カタログからカードと解説ページを再生成します。')],
        'commandNote': 'スキル名またはSKILL.mdのパスをCodexに伝えます。生成元を更新してから再生成します。',
        'flow': [('tool', 'スキル定義を読む', '指示書と必要な参照・スクリプトを確認。'), ('llm', '紹介内容を作成', '依頼例・入力・出力・制約を説明。'), ('tool', 'カタログに登録', 'SKILLSとINTRO_DETAILSを追加・同期。'), ('det', 'ページを再生成', '共通のカードと解説テンプレートへ反映。'), ('tool', '導線・表示を確認', '一覧・解説・戻るリンクと画面幅を確認。')],
        'details': [('生成元を編集', 'skill_catalog.pyに紹介を登録します。idはfrontmatterのnameに、pathは実在する定義ファイルに合わせます。生成済みHTMLを直接編集しません。'), ('定義に合う説明', '受付可能な依頼例、処理の流れ、構成ファイル、制約を説明します。存在しないコマンドや承認手順を足しません。')],
        'files': [('SKILL.md', 'カタログ登録と表示確認の手順。'), ('Kyoto_Univ/skill_catalog.py', '紹介内容と解説ページ生成処理。'), ('Kyoto_Univ/update_portal.py', '一覧と紹介ページを再生成する入口。')],
        'limit': 'このリポジトリのLIFEカタログ用です。スキル定義自体の作成や機能変更はskill-creatorで扱います。',
    },
    {
        'id': 'math-engineering-report-check', 'title': '数理工学実験レポート点検', 'icon': 'scroll',
        'path': '.codex/skills/math-engineering-report-check/SKILL.md',
        'overview': '数理工学実験の完成したLaTeXレポートを教材の全設問と照合し、問題文、解答、コード、結果、文章作法、AI利用の記載を点検します。',
        'commands': [
            ('$math-engineering-report-check 数値線形代数のレポートを点検して', '対象の.texと関連するコード・図・データを指定。教材第2章の設問と照合します。'),
            ('$math-engineering-report-check この.texの未回答と説明ミスを厳格に確認して', '対象テーマを指定。設問ごとの対応表と根拠付きの指摘を作ります。'),
        ],
        'commandNote': 'Codexへの自然言語の依頼例です。完成原稿と対象テーマを指定します。専用CLIや採点コマンドはありません。',
        'flow': [('tool', '原典と提出物を確認', '教材・ガイダンス、.tex、コード、図、データを読む。'), ('llm', '全設問を列挙', '原本画像で問題文を照合し、必須・任意・小問を分ける。'), ('llm', '本文と結果を検証', '設問の回答、定義・単位、理論との比較、文章と引用を点検。'), ('tool', '実行と組版を確認', '可能ならコードの再実行とLaTeXビルドを行う。'), ('llm', '根拠付きで報告', '設問対応表、重大度、修正方針、未確認事項を示す。')],
        'details': [
            ('設問を小問まで追跡', 'テーマ番号と教材の章番号を区別し、章の全ページを確認します。問題文の条件・数式を原本で照合し、必須と任意を分けて、回答箇所と不足を対応表にします。'),
            ('科学レポートとしての説明', '表紙、要約、課題と手法、実験結果と考察、結論、参考文献を確認します。事実と考察、初出の物理量・単位、図表の番号とキャプション、理論値との比較、原典を確認した引用を重視します。'),
            ('AI利用と提出物', 'コード・レポート・ひな形作成に生成AIを使った場合の明記と引用を確認します。残留プロンプトなどの具体的な矛盾は指摘しますが、文体だけで無申告利用とは断定しません。ガイダンスが求める動作するコード等との整合も確認します。'),
            ('指摘の読み方', '重大・重要・軽微の順に、原稿位置、原典ページ、理由、修正方針を示します。実行やビルドができない場合、または証拠が足りない場合は未確認として残します。'),
        ],
        'files': [('SKILL.md', '教材・提出物の照合手順と点検結果の形式。'), ('references/review-criteria.md', 'ガイダンスの規則と依頼者指定の文章作法・AI利用基準。')],
        'limit': '専用の自動採点器ではありません。AI利用の有無や本人の理解を文体から証明できず、確認できない点は未確認とします。合否を保証しません。',
    },
    {
        'id': 'math-engineering-report-template', 'title': '数理工学実験レポートひな形', 'icon': 'pen',
        'path': '.codex/skills/math-engineering-report-template/SKILL.md',
        'overview': '指定した実験テーマの全設問を教材PDFと照合して載せ、解法・コード・数値結果・考察を学生が自分で埋めるLaTeXひな形を作ります。',
        'commands': [
            ('$math-engineering-report-template 数値線形代数のレポートひな形を作って', '教材第2章の問題を確認し、本人が記入する.texを作ります。'),
            ('$math-engineering-report-template 熱方程式の差分法のひな形を作って', '対象章の必須・任意設問を区別し、問題文と記入欄を用意します。'),
        ],
        'commandNote': 'Codexへの自然言語の依頼例です。実験テーマと、必要なら保存先・LaTeX環境を伝えます。専用CLIや固定フラグはありません。',
        'flow': [('tool', '教材とガイダンスを確認', '対象テーマと教材の章を対応付け、全ページを読む。'), ('llm', '問題文を照合して転記', '原本画像で条件・数式・小問を確認し、任意課題を区別。'), ('llm', '本人用の記入欄を設計', '方法、コード、結果、理論との比較、考察の欄を用意。'), ('tool', 'LaTeXを作成・確認', '編集可能な.texを保存し、可能ならビルドする。'), ('llm', '未記入と未確認を報告', '転記の不確かさと、学生が完成させる箇所を示す。')],
        'details': [
            ('原典の問題を載せる', '教材の対象章を全ページ確認し、章末だけでなく本文中の実験課題や小問も拾います。抽出文字だけに頼らずPDF原本で照合し、読めない箇所は推測せずTODOとして示します。'),
            ('学習を妨げない空欄', '表紙、要約、方法、結果、考察、結論、参考文献、AI利用の欄を設けます。コード掲載または外部コードファイルの欄も用意します。完成した解法・コード・数値結果・考察は埋めません。'),
            ('提出前に自分で確認する点', '図表番号とキャプション、記号と単位、理論との比較、事実と考察の区別を記入指示に含めます。生成AIによるひな形作成を開示できる欄を設け、本人が使ったAIと検証内容を追記できるようにします。'),
        ],
        'files': [('SKILL.md', 'テーマの全設問を確認し、未完成のLaTeXひな形を作る手順。'), ('対象テーマの.tex', '依頼時に作る、問題文と本人用記入欄を含むレポートひな形。')],
        'limit': 'ひな形は完成レポートではありません。問題文が判読できない箇所は未確認のまま示し、実験・検証・説明は学生本人が行います。',
    },
])

SKILLS.append({
    'id': 'article-explainer', 'title': '記事解説', 'icon': 'book',
    'path': '.codex/skills/article-explainer/SKILL.md',
    'overview': '原典を引用しながら、記事の主張と理由を文章で解説します。用語はその場のトグルで補い、図や補助スライドで理解を助けます。',
    'commands': [('$article-explainer この記事を解説して https://example.com/article', 'URLから記事本文を確認して解説を保存します。'), ('$article-explainer 次の記事全文を解説して：〈全文〉', '貼り付けた記事を原典として解説します。'), ('$article-explainer この画像の記事を解説して', '記事のスクリーンショットを添付して依頼します。')],
    'commandNote': 'CodexのチャットでURL・記事全文・画像を渡します。LIFEのHTML画面からは生成できません。保存済みの解説はローカルファイルからも読めます。',
    'flow': [('tool', '記事を読む', '本文・画像の文字と図表・タイトル・執筆時を確認。'), ('tool', '既知知識を確認', 'リポジトリの関連資料を実際に読む。'), ('llm', '解説と図表を作る', '原典の引用を短く示し、意味・理由・例を文章で解説。用語はその場で補足。'), ('det', '履歴として保存・表示', '本文と補助図を検証し、記事執筆時と生成日時付きで表示。')],
    'details': [('引用を読み解く文章中心の解説', '「この記事が言いたいこと」から「解説」へ進みます。原典の短い引用と出典を示し、意味・理由・具体例を文章でつなぎます。用語や前提知識は登場する場所のトグルで説明します。資料の図表・式を解説するときは、原図や該当箇所の抜粋をその場に表示します。'), ('既知知識からつなぐ', '関連する学習資料やメモの記載を既知知識として扱い、用語や仕組みの差分を補います。参照したファイルと概念を明記します。'), ('業界の背景を補う', '主要プレイヤー、事業・技術の構造、実務のトレードオフや争点を記事に合わせて選びます。変わり得る情報は外部資料で確認し、記事執筆時点と生成時点を区別します。'), ('しおり・入力元・読書ステータス', '見出し左の小さな金枠の円でしおりを付けると、次回そこから再開できます。補助スライドは丸い矢印ボタンで移動します。入力したURLや文章は折りたたみ欄、読書ステータスは記事ごとに保存します。'), ('日付と履歴', '執筆時が不明なら不明とし、公開日の代用は明示します。生成日時は日本時間で保存し、過去の解説も履歴に残します。')],
    'files': [('SKILL.md', '記事の読解、既知知識の照合、解説と保存の手順。'), ('Kyoto_Univ/article_reports.py', '解説を保存し一覧・詳細の表示データを生成。'), ('article_management/ID.json', '記事ごとの解説と日時。')],
    'limit': 'URLの記事を読むにはWeb閲覧が必要です。アクセスできない本文を推測しません。リポジトリの記載を既知知識とみなすことは実際の習熟の測定ではありません。',
})

LABELS = {'det': '決定論・スクリプト', 'tool': 'ツール処理', 'llm': 'LLM・読解／判断', 'human': 'ユーザー確認'}
INTRO_DETAILS = {
    'article-explainer': '文章を読み進めながら、必要な用語トグルを開けます。図や補助スライドを本文に添え、節ごとのしおりで続きから再開できます。',
    'goal-summary': '指定Notionの6件の目標を各ページの本文まで確認します。サマリは短い表で整理し、目標一覧の日付をクリックすると読めます。',
    'skill-catalog-entry': '対象スキルの実際の定義と紹介を対応させます。カタログに登録すると、共通デザインのカードと解説ページが生成されます。',
    'math-engineering-report-check': '完成した.texに加え、提出予定のコード・図・データがあれば照合します。必須と任意の設問を分け、問題文の記載、結果の検証、文章作法、AI利用の開示を根拠付きで確認します。',
    'math-engineering-report-template': '指定した七つの実験テーマのうち一つを対象にします。教材の問題文を原本と照合して載せ、解法・コード・結果・考察は学生が自分で書く欄として残します。',
    'university-stem-study': '科目、対象の章や授業回、原典、過去問・演習、自分の途中式を入力として扱います。初学時の補助説明と復習時の参照情報を分け、問題の特徴から道具を選び、条件を確認して解くための資料へつなげます。',
    'lecture-slide-explainer': '理系以外の講義にも対応します。対象PDFに加えて資料一覧・先行解説・過去問や課題を確認し、何を意味し、なぜそうなり、問題でどう使うかを解説します。LIFE科目ページはmockと微分積分学続論IIの構成・UIを厳守し、開閉式目次、要旨、1枚ごとの解説と原スライド画像を対応させます。',
    'handwritten-lecture-explainer': '板書写真・手書きPDFを入力に、原画像とOCRを照合して授業回ごとの独立した解説HTMLを作ります。スライド解説と異なり、元画像を本文に併記しません。出典位置と判読不能箇所は記録し、講義内容は文章・数式・必要な説明用の図で伝えます。',
    'kyoto-past-exams': '教科名・ファイル名に使われる教員名・履修年度を入力して検索します。教員名は必須で、未入力では開始できません。名前の3条件と内容の4種類を分け、ファイル名をタイトルにしてDriveリンクを表示します。未走査領域はパスとURLを末尾に残します。',
    'explain': '対象はファイル・ディレクトリ・テーマです。保存先と読者レベルに合わせて構成を設計し、引用と図から実装をたどれるMarkdown資料を作成します。機械的な参照検査とLLMによる説明の確認を組み合わせて、既存資料の更新にも対応します。',
}


def icon(name):
    return f'<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#{escape(name)}"/></svg>'


def build_skills(shell):
    cards = []
    directory = ROOT / 'ui' / 'skills'
    directory.mkdir(parents=True, exist_ok=True)
    for skill in SKILLS:
        source = REPO / skill['path']
        if not source.is_file():
            continue
        definition = source.read_text(encoding='utf-8')
        name = re.search(r'^name:\s*(.+)$', definition, re.M)
        if not name or name[1].strip() != skill['id']:
            raise ValueError(f'Skill name does not match catalog: {source}')
        summary = skill['overview']
        title = escape(name[1].strip())
        subtitle = escape(skill['title'])
        slug = skill['id']
        cards.append(f'<a class="skill-card" href="ui/skills/{slug}.html"><div class="skill-card-heading">{icon(skill["icon"])}<div><h2>{title}</h2><p class="skill-subtitle">{subtitle}</p></div></div><p class="skill-card-summary">{escape(summary)}</p></a>')
        commands = ''.join(f'<li><code>{escape(command)}</code><p>{escape(note)}</p></li>' for command, note in skill['commands'])
        flow = ''.join(f'<li class="flow-node flow-{kind}"><span class="flow-label">{LABELS[kind]}</span><h3>{escape(name)}</h3><p>{escape(note)}</p></li>' for kind, name, note in skill['flow'])
        details = ''.join(f'<h3>{escape(name)}</h3><p>{escape(note)}</p>' for name, note in skill['details'])
        files = ''.join(f'<tr><th scope="row"><code>{escape(name)}</code></th><td>{escape(note)}</td></tr>' for name, note in skill['files'])
        active_shell = shell.replace('data-section="スキル"', 'data-section="スキル" class="active" aria-current="page"').replace('data-section="授業資料" class="active" aria-current="page"', 'data-section="授業資料"')
        page = f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}｜LIFE スキル</title><link rel="stylesheet" href="../life.css"><script defer src="../life.js"></script></head>
<body data-life-page="skill" data-portal="../../index.html"><div class="shell">{active_shell}<main>
<article class="skill-document">
<header class="page-head skill-head detail-head"><a class="back-step" href="../../index.html#section=%E3%82%B9%E3%82%AD%E3%83%AB" aria-label="スキル一覧に戻る"><svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg></a><div class="skill-heading-text"><h1>{title}</h1><p class="skill-subtitle">{subtitle}</p></div></header>
<p class="skill-intro">{escape(skill['overview'])}</p><p class="skill-intro">{escape(INTRO_DETAILS[slug])}</p>
<nav class="skill-toc" aria-label="このスキルの紹介"><a href="#commands">コマンド一覧</a><a href="#structure">構造図</a><a href="#details">詳細な解説</a></nav>
<section id="commands"><h2>受付可能なコマンド一覧</h2><p>{escape(skill['commandNote'])}</p><ul class="skill-commands">{commands}</ul></section>
<section id="structure"><h2>スキルの構造図</h2>
<p class="flow-legend"><span class="legend-det">決定論：同じ入力に同じ規則を適用</span><span class="legend-llm">LLM：内容の読解・判断・生成</span></p>
<ol class="skill-flow" aria-label="処理の流れ">{flow}</ol><p class="skill-note">{escape(skill['limit'])}</p>
<h3>ファイル構成</h3><div class="skill-file-table"><table><thead><tr><th scope="col">ファイル</th><th scope="col">役割</th></tr></thead><tbody>{files}</tbody></table></div></section>
<section id="details"><h2>詳細な解説</h2>{details}</section>
<footer class="skill-source"><p>定義元：<code>{escape(skill['path'])}</code></p><a href="../../index.html#section=%E3%82%B9%E3%82%AD%E3%83%AB">← スキル一覧に戻る</a></footer>
</article></main></div></body></html>'''
        (directory / f'{slug}.html').write_text(page, encoding='utf-8')
    return '\n'.join(cards)
