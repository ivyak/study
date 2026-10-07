"""Notion HTTP API クライアント.

実装範囲:
  - ``POST /v1/pages``  : ページ新規作成 (DB 内 / ページ配下)
  - ``PATCH /v1/blocks/:page_id/children`` : ブロックを 100 件ごとに chunk 追加
  - ``GET /v1/pages/:id/markdown`` : ページ Markdown 読み取り
  - ``PATCH /v1/pages/:id/markdown`` : テキスト search-and-replace 更新 (Markdown API)
  - ``GET /v1/pages/:id`` : ページプロパティ取得
  - ``PATCH /v1/pages/:id`` : ページプロパティ更新
  - ``PATCH /v1/blocks/:id`` : 個別ブロック更新
  - ``DELETE /v1/blocks/:id`` : ブロック削除
  - ``POST /v1/databases/:id/query`` : DB クエリ
  - ``GET /v1/databases/:id`` : DB 情報取得
  - ``GET /v1/data_sources/:id`` : DB プロパティ取得 (data_source 経由)
  - ``POST /v1/comments`` : コメント追加
  - ``GET /v1/comments`` : コメント取得
  - ``POST /v1/file_uploads`` : ファイルアップロード (3 ステップ)
  - 429 / 5xx を指数バックオフでリトライ

Notion API は 1 リクエストあたり children 100 件 + 階層深さの制約がある。
heading_2 (is_toggleable=true) の ``children`` までは一度の append で送ってよい。
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)
# ログは stderr に出す (CLI の stdout を汚さないため)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.WARNING)
    logger.addHandler(_handler)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

# リトライ対象ステータス
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
# 指数バックオフ基準秒（1, 2, 4, 8, 16）
_BACKOFF_BASE = (1.0, 2.0, 4.0, 8.0, 16.0)


class NotionAPIError(RuntimeError):
    """Notion API のエラーを表す例外."""

    def __init__(self, message: str, *, status_code: int, body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class NotionClient:
    """Notion API への薄いラッパ. リトライとロギングのみ持たせる."""

    def __init__(
        self,
        api_token: str,
        *,
        version: str = NOTION_VERSION,
        timeout: float = 60.0,
        max_retries: int = 0,
    ) -> None:
        # append_children / create_page は非冪等（重複ブロック生成リスク）のため
        # リトライはデフォルト無効。明示指定時のみ有効化する。
        self._api_token = api_token
        self._version = version
        self._timeout = timeout
        self._max_retries = max_retries

    # ---- public API -----------------------------------------------------

    def create_page(
        self,
        *,
        parent_page_id: str,
        title: str,
        icon: str | None = None,
        children: list[dict] | None = None,
    ) -> dict:
        """新規ページを作成して JSON を返す.

        ``children`` を渡す場合、Notion API は最大 100 件 + 階層深さ 2 まで受け付ける。
        通常は **空 children でページだけ作成** → :meth:`append_children` で追記する運用を推奨。
        """
        payload: dict[str, Any] = {
            "parent": {"page_id": parent_page_id},
            "properties": {
                "title": {"title": [{"type": "text", "text": {"content": title}}]}
            },
        }
        if icon:
            # 絵文字 1 文字 or 外部 URL を icon とする
            payload["icon"] = (
                {"type": "external", "external": {"url": icon}}
                if icon.startswith(("http://", "https://"))
                else {"type": "emoji", "emoji": icon}
            )
        if children:
            payload["children"] = children

        return self._request("POST", "/pages", json=payload)

    def append_children(
        self,
        block_id: str,
        children: list[dict],
        *,
        chunk_size: int = 90,
        after: str | None = None,
        position_start: bool = False,
    ) -> list[dict]:
        """``block_id`` に children を Notion API の depth=2 制約に合わせて多段投入する.

        挿入位置:
          - 既定: 末尾に追記
          - ``after=<block_id>``: そのブロックの直後(親の直接の子でなければ API が 400)
          - ``position_start=True``: 先頭

        位置指定時も 100 件制約に合わせてチャンク投入する(2 チャンク目以降は直前チャンクの
        最後のブロックの後ろに差し込む)。position 付き API は挿入位置以降の既存ブロックも
        results に含めるため、投入前の子 ID を控えて **今回作成した分だけ** を返す。

        投入戦略:
          1. 全ブロックを :meth:`_strip_children_recursive` で「depth=2 の安全形」に整形
             - children 不要なブロック(toggle など)の ``children`` は剥がす
             - children 必須なブロック(column_list / column / table)は children を保持、
               ただし内部の各ブロックの children は再帰的に strip
          2. 整形した shallow blocks を PATCH で投入
          3. 投入結果と元ブロックを突き合わせ、deep children を持つブロックを探す
             - children 不要ブロック: 元 children を再帰 :meth:`append_children`
             - children 必須ブロック: 内部 ID を :meth:`get_block_children` で取得し、
               内部の各ブロックに対して再帰的に :meth:`_process_deep_children` を実行
        """
        if chunk_size < 1 or chunk_size > 100:
            raise ValueError("chunk_size は 1〜100 の範囲で指定してください")
        if after and position_start:
            raise ValueError("after と position_start は同時に指定できません")

        shallow = [self._strip_children_recursive(block) for block in children]
        positioned = bool(after) or position_start
        known_ids: set[str] = set()
        if positioned:
            known_ids = {b["id"] for b in self.get_block_children(block_id)}

        results: list[dict] = []
        last_new_id: str | None = None
        n_chunks = (len(shallow) + chunk_size - 1) // chunk_size
        for i in range(0, len(shallow), chunk_size):
            chunk = shallow[i : i + chunk_size]
            payload: dict[str, Any] = {"children": chunk}
            if positioned:
                if last_new_id:
                    payload["position"] = {"type": "after_block", "after_block": {"id": last_new_id}}
                elif after:
                    payload["position"] = {"type": "after_block", "after_block": {"id": after}}
                else:
                    payload["position"] = {"type": "start"}
            logger.info(
                "append_children: parent=%s chunk=%d/%d (%d items)",
                block_id, (i // chunk_size) + 1, n_chunks, len(chunk),
            )
            resp = self._request("PATCH", f"/blocks/{block_id}/children", json=payload)
            created = [r for r in resp.get("results", []) if r["id"] not in known_ids]
            if positioned:
                created = created[: len(chunk)]
                known_ids.update(r["id"] for r in created)
                if created:
                    last_new_id = created[-1]["id"]
            results.extend(created)

        if len(results) != len(children):
            logger.warning(
                "作成ブロック数が一致しません (created=%d, requested=%d, parent=%s)",
                len(results), len(children), block_id,
            )
        # 元 children と作成済みブロックを突き合わせ、深いネストを処理
        for original, created_block in zip(children, results):
            self._process_deep_children(original, created_block["id"], chunk_size=chunk_size)
        return results

    def get_block_children(self, block_id: str) -> list[dict]:
        """``GET /v1/blocks/:id/children`` で直下 children を順序付きで全件取得."""
        results: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = self._request("GET", f"/blocks/{block_id}/children", params=params)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    # ---- 読み取り --------------------------------------------------------

    def read_page_markdown(self, page_id: str) -> dict:
        """``GET /v1/pages/:id/markdown`` でページ全文を Markdown で取得."""
        return self._request("GET", f"/pages/{page_id}/markdown")

    def get_page(self, page_id: str) -> dict:
        """``GET /v1/pages/:id`` でページプロパティを取得."""
        return self._request("GET", f"/pages/{page_id}")

    def get_block(self, block_id: str) -> dict:
        """``GET /v1/blocks/:id`` で単一ブロック (メタ情報) を取得.

        ``parent`` フィールドに ``page_id`` / ``block_id`` / ``database_id`` の
        いずれかが入るので、``--after`` の親解決などに使う。
        """
        return self._request("GET", f"/blocks/{block_id}")

    def search(
        self,
        *,
        query: str | None = None,
        filter_type: str | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """``POST /v1/search`` で共有されているページ / DB を検索する.

        ``filter_type`` は ``"page"`` か ``"database"`` を指定可能 (Notion の
        ``filter.value``)。``query`` 省略時は全件 (アクセス可能なもの) を返す。
        """
        results: list[dict] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": page_size}
            if query:
                payload["query"] = query
            if filter_type:
                payload["filter"] = {"property": "object", "value": filter_type}
            if cursor:
                payload["start_cursor"] = cursor
            resp = self._request("POST", "/search", json=payload)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    # ---- ページプロパティ更新 --------------------------------------------

    def update_page(self, page_id: str, *, properties: dict) -> dict:
        """``PATCH /v1/pages/:id`` でページプロパティを更新."""
        return self._request("PATCH", f"/pages/{page_id}", json={"properties": properties})

    # ---- Markdown API (テキスト更新) ------------------------------------

    def update_content(
        self,
        page_id: str,
        *,
        old_str: str,
        new_str: str,
        replace_all: bool = False,
    ) -> dict:
        """Markdown API で search-and-replace."""
        update = {"old_str": old_str, "new_str": new_str}
        if replace_all:
            update["replace_all_matches"] = True
        return self._request(
            "PATCH",
            f"/pages/{page_id}/markdown",
            json={"type": "update_content", "update_content": {"content_updates": [update]}},
        )

    # ---- ブロック操作 (個別) --------------------------------------------

    def update_block(self, block_id: str, *, block_data: dict) -> dict:
        """``PATCH /v1/blocks/:id`` で個別ブロックを更新."""
        return self._request("PATCH", f"/blocks/{block_id}", json=block_data)

    def delete_block(self, block_id: str) -> dict:
        """``DELETE /v1/blocks/:id`` でブロックを削除 (アーカイブ)."""
        return self._request("DELETE", f"/blocks/{block_id}")

    # ---- データベース操作 ------------------------------------------------

    def query_database(self, db_id: str, *, filter: dict | None = None) -> list[dict]:
        """DB のページ一覧を全件取得.

        Notion API 2026-03-11 では ``/databases/{id}/query`` が廃止され、
        ``/data_sources/{ds_id}/query`` に移行した。
        db_id が渡された場合は GET /databases/{id} → data_sources[0].id を取得してからクエリする。
        data_source_id が直接渡された場合はそのまま使う。
        """
        ds_id = self._resolve_data_source_id(db_id)
        results: list[dict] = []
        cursor: str | None = None
        while True:
            payload: dict[str, Any] = {"page_size": 100}
            if filter:
                payload["filter"] = filter
            if cursor:
                payload["start_cursor"] = cursor
            resp = self._request("POST", f"/data_sources/{ds_id}/query", json=payload)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def _resolve_data_source_id(self, db_or_ds_id: str) -> str:
        """db_id から data_source_id を解決する. 既に ds_id なら検証してそのまま返す."""
        # まず data_source として直接試行
        try:
            resp = self._request("GET", f"/data_sources/{db_or_ds_id}")
            if resp.get("object") == "data_source":
                return db_or_ds_id
        except Exception:
            pass
        # database_id として data_sources を取得
        db = self.get_database(db_or_ds_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            raise RuntimeError(f"DB {db_or_ds_id} に data_sources がありません")
        return data_sources[0]["id"]

    def get_database(self, db_id: str) -> dict:
        """``GET /v1/databases/:id`` で DB 情報を取得."""
        return self._request("GET", f"/databases/{db_id}")

    def get_data_source(self, data_source_id: str) -> dict:
        """``GET /v1/data_sources/:id`` で DB プロパティを取得."""
        return self._request("GET", f"/data_sources/{data_source_id}")

    def get_db_schema(self, db_id: str) -> dict:
        """DB プロパティを 2 ステップで取得 (database → data_source)."""
        db = self.get_database(db_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            raise RuntimeError(f"DB {db_id} に data_sources がありません")
        ds_id = data_sources[0]["id"]
        return self.get_data_source(ds_id)

    def create_database_page(self, db_id: str, *, properties: dict) -> dict:
        """DB 内に新規ページを作成."""
        return self._request(
            "POST",
            "/pages",
            json={"parent": {"database_id": db_id}, "properties": properties},
        )

    # ---- コメント --------------------------------------------------------

    def get_comments(self, page_id: str) -> list[dict]:
        """``GET /v1/comments`` でページコメントを取得."""
        results: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"block_id": page_id, "page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = self._request("GET", "/comments", params=params)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return results

    def add_comment(self, page_id: str, *, text: str) -> dict:
        """``POST /v1/comments`` でページコメントを追加."""
        return self._request(
            "POST",
            "/comments",
            json={
                "parent": {"page_id": page_id},
                "rich_text": [{"type": "text", "text": {"content": text}}],
            },
        )

    # ---- ファイルアップロード (3 ステップ) --------------------------------

    def upload_file(self, file_path: str) -> str:
        """ファイルをアップロードして file_upload ID を返す."""
        import mimetypes

        # Step 1: アップロードオブジェクト作成
        upload_resp = self._request(
            "POST", "/file_uploads", json={"mode": "single_part"}
        )
        upload_id = upload_resp["id"]

        # Step 2: ファイル送信 (multipart なので _request は使わず直接)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        url = f"{NOTION_API_BASE}/file_uploads/{upload_id}/send"
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Notion-Version": self._version,
        }
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                headers=headers,
                files={"file": (file_path.split("/")[-1], f, mime_type)},
                timeout=self._timeout,
            )
        if response.status_code >= 400:
            raise NotionAPIError(
                f"ファイルアップロード失敗: HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text[:600],
            )
        return upload_id

    # children が構造上必須で、strip すると API が rejects するブロック種
    # - table: table_row が必須
    # - column_list: 最低 2 個の column が必須
    # - column: 中身（paragraph 等）が必須
    _CHILDREN_REQUIRED_TYPES = frozenset({"table", "column_list", "column"})

    @classmethod
    def _strip_children_recursive(cls, block: dict) -> dict:
        """block を API の depth=2 制約に合わせて再帰的に shallow 化する.

        children 必須ブロックは children を保持しつつ、内部の各ブロックを再帰で
        shallow 化する。children 不要ブロックは ``children`` フィールドごと剥がす。
        """
        t = block["type"]
        body = block[t]
        if t in cls._CHILDREN_REQUIRED_TYPES:
            inner = body.get("children")
            if inner is not None:
                new_inner = [cls._strip_children_recursive(c) for c in inner]
                return {"type": t, t: {**body, "children": new_inner}}
            return block
        new_body = {k: v for k, v in body.items() if k != "children"}
        return {"type": t, t: new_body}

    def _process_deep_children(
        self,
        original: dict,
        created_id: str,
        *,
        chunk_size: int,
    ) -> None:
        """``original`` ブロックに保持されていた deep children を、``created_id`` 側に反映."""
        t = original["type"]
        body = original[t]
        if t in self._CHILDREN_REQUIRED_TYPES:
            original_inner = body.get("children") or []
            if not original_inner:
                return
            # children 必須ブロックの内部は既に shallow 化して投入済み。
            # 内部の各ブロックの deep children を投入するため、API から内部 ID を取得する
            created_inner = self.get_block_children(created_id)
            if len(created_inner) < len(original_inner):
                logger.warning(
                    "内部ブロック数が一致しません (created=%d, original=%d, parent=%s)",
                    len(created_inner),
                    len(original_inner),
                    created_id,
                )
            for orig_c, created_c in zip(original_inner, created_inner):
                self._process_deep_children(
                    orig_c, created_c["id"], chunk_size=chunk_size
                )
        else:
            deep = body.get("children") or []
            if deep:
                self.append_children(created_id, deep, chunk_size=chunk_size)

    # ---- internal -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Notion-Version": self._version,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """共通リクエスト処理. リトライとエラーハンドリング込み."""
        url = f"{NOTION_API_BASE}{path}"
        last_error: NotionAPIError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                    timeout=self._timeout,
                )
            except requests.RequestException as e:
                # ネットワーク瞬断もリトライ対象
                wait = self._backoff_seconds(attempt)
                logger.warning(
                    "%s %s でネットワーク例外: %s (retry %d/%d, wait %.1fs)",
                    method,
                    path,
                    e,
                    attempt + 1,
                    self._max_retries,
                    wait,
                )
                if attempt >= self._max_retries:
                    raise
                time.sleep(wait)
                continue

            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError:
                    raise NotionAPIError(
                        f"{method} {path}: 応答が JSON ではありません",
                        status_code=response.status_code,
                        body=response.text[:600],
                    )

            body_preview = response.text[:600]
            if (
                response.status_code in _RETRYABLE_STATUSES
                and attempt < self._max_retries
            ):
                wait = self._backoff_seconds(attempt, response=response)
                logger.warning(
                    "%s %s が %s 応答 (retry %d/%d, wait %.1fs): %s",
                    method,
                    path,
                    response.status_code,
                    attempt + 1,
                    self._max_retries,
                    wait,
                    body_preview,
                )
                time.sleep(wait)
                continue

            last_error = NotionAPIError(
                f"{method} {path} 失敗: HTTP {response.status_code}",
                status_code=response.status_code,
                body=body_preview,
            )
            logger.error(
                "%s %s 失敗 %s: %s", method, path, response.status_code, body_preview
            )
            raise last_error

        # ここに来るのはネットワーク例外でリトライ上限超過した場合のみ
        raise RuntimeError(f"{method} {path}: リトライ上限を超過")

    @staticmethod
    def _backoff_seconds(
        attempt: int, *, response: requests.Response | None = None
    ) -> float:
        """次回リトライまでの待機秒数. ``Retry-After`` があれば優先."""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        base = _BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)]
        # jitter ±25%
        return base * (0.75 + random.random() * 0.5)
