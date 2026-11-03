# 家計DBの全列定義

実装モデルから生成した全11テーブル。FKは別の表のIDを保存する列。transactions.identity_keyは取引のIDを更新後も維持するため、設計図に追加した固定キー。

idは各表の主キー。金額はDecimalField。JSONは元行の全列や確認案など可変構造を保持する。

ユーザーが許可した「不明」は収入・支出で同じ表示カテゴリを使用する。仕訳の勘定は費用「不明」と収益「不明（収入）」を区別し、カテゴリ名から収支の向きを推測しない。追加の列は不要。

```mermaid
erDiagram
  import_batches ||--o{ raw_occurrences : batch_id
  import_files ||--o{ raw_occurrences : import_file_id
  raw_records ||--o{ raw_occurrences : raw_record_id
  accounts ||--o{ categories : account_id
  import_batches ||--o{ transactions : last_batch_id
  transactions ||--o{ transaction_items : transaction_id
  categories ||--o{ transaction_items : category_id
  raw_records o|--o{ transaction_items : source_raw_record_id
  transactions ||--o{ journal_entries : transaction_id
  accounts ||--o{ journal_entries : account_id
  transactions ||--o{ transaction_sources : transaction_id
  raw_records ||--o{ transaction_sources : raw_record_id
  import_batches ||--o{ decisions : batch_id
  import_batches {
    bigint id PK "NULL不可"
    string status "NULL不可"
    datetime started_at "NULL不可"
    datetime published_at "NULL可"
    json proposed_changes "NULL不可"
    text backup_path "NULL不可"
    text error_message "NULL不可"
  }
  import_files {
    bigint id PK "NULL不可"
    string source "NULL不可"
    text original_name "NULL不可"
    string file_hash "NULL不可"
    string encoding "NULL不可"
    string parser_version "NULL不可"
    datetime imported_at "NULL不可"
  }
  raw_records {
    bigint id PK "NULL不可"
    string source "NULL不可"
    string dedupe_scope "NULL不可"
    string dedupe_key "NULL不可"
    integer occurrence_number "NULL不可"
    string source_transaction_id "NULL不可"
    json raw_data "NULL不可"
    date transaction_date "NULL可"
    decimal amount "NULL可"
    string currency "NULL不可"
    string direction "NULL不可"
    string account_hint "NULL不可"
    string counterparty_hint "NULL不可"
    text store "NULL不可"
    text memo "NULL不可"
    text item_name "NULL不可"
    string category_name "NULL不可"
    string subcategory_name "NULL不可"
    string billing_month "NULL不可"
    decimal balance "NULL可"
    datetime created_at "NULL不可"
  }
  raw_occurrences {
    bigint id PK "NULL不可"
    bigint batch_id FK "NULL不可"
    bigint import_file_id FK "NULL不可"
    bigint raw_record_id FK "NULL不可"
    integer line_start "NULL不可"
    integer line_end "NULL不可"
  }
  accounts {
    bigint id PK "NULL不可"
    string name "NULL不可"
    string type "NULL不可"
    string currency "NULL不可"
    date balance_start_date "NULL可"
  }
  categories {
    bigint id PK "NULL不可"
    string name "NULL不可"
    string color "NULL不可"
    bigint account_id FK "NULL不可"
    integer position "NULL不可"
  }
  transactions {
    bigint id PK "NULL不可"
    string identity_key "NULL不可"
    date date "NULL不可"
    string kind "NULL不可"
    text title "NULL不可"
    decimal amount "NULL不可"
    string currency "NULL不可"
    bigint last_batch_id FK "NULL不可"
    datetime created_at "NULL不可"
    datetime updated_at "NULL不可"
  }
  transaction_items {
    bigint id PK "NULL不可"
    bigint transaction_id FK "NULL不可"
    bigint category_id FK "NULL不可"
    bigint source_raw_record_id FK "NULL可"
    text name "NULL不可"
    text store "NULL不可"
    string subcategory "NULL不可"
    decimal amount "NULL不可"
    decimal receipt_amount "NULL可"
    integer position "NULL不可"
  }
  journal_entries {
    bigint id PK "NULL不可"
    bigint transaction_id FK "NULL不可"
    bigint account_id FK "NULL不可"
    decimal debit "NULL不可"
    decimal credit "NULL不可"
    integer position "NULL不可"
  }
  transaction_sources {
    bigint id PK "NULL不可"
    bigint transaction_id FK "NULL不可"
    bigint raw_record_id FK "NULL不可"
    string role "NULL不可"
    decimal linked_amount "NULL不可"
  }
  decisions {
    bigint id PK "NULL不可"
    bigint batch_id FK "NULL不可"
    string kind "NULL不可"
    string status "NULL不可"
    json targets "NULL不可"
    json proposal "NULL不可"
    text reason "NULL不可"
    text question "NULL不可"
    text user_answer "NULL不可"
    json before "NULL可"
    json after "NULL可"
    datetime created_at "NULL不可"
    datetime confirmed_at "NULL可"
  }
```

主な制約：元行キーの一意性、元行取得元の一意性、勘定・カテゴリ名の一意性、仕訳の借方・貸方が非負で、両方が正数にならないこと。両方0は0円の開始残高に限り確定処理で許可すること。取引全体の貸借一致・内訳一致・二重使用は確定処理でまとめて検証する。
