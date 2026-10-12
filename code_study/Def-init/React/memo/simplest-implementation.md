# 課題2（ContactForm）の最小実装例

課題の要件を満たす、できるだけ短い実装です。スタイルは省いています。

## 全体の構造

この課題で覚えたいのは、「**状態は親が持ち、子は表示と通知だけを担当する**」という形です。

```
            App（formState を持つ）
             │                ▲
  props で渡す│                │コールバックで知らせる
 formState    │                │onChange(key, value)
             ▼                │onSubmit(values)
        ContactForm（state を持たない）
```

- **データは上から下へ**: `App` が `formState` を props で `ContactForm` に渡します。`ContactForm` はそれを表示するだけです。
- **イベントは下から上へ**: 入力や送信があると、`ContactForm` は `onChange` や `onSubmit` を呼んで `App` に知らせます。値を書き換えるのは `App` です。

`ContactForm` は自分で状態を持たないので、「同じ props を渡せば、いつも同じ見た目になる」コンポーネントになります。こうしておくと、テストしやすく、別の画面でも使い回しやすくなります。

## ContactForm.tsx

```tsx
export type ContactFormValues = { name: string; email: string; message: string };

type Props = {
  formState: ContactFormValues;
  onChange: (key: keyof ContactFormValues, value: string) => void;
  onSubmit: (values: ContactFormValues) => void;
};

export function ContactForm({ formState, onChange, onSubmit }: Props) {
  const isEmpty = Object.values(formState).some((v) => v.trim() === "");

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!isEmpty) onSubmit(formState);
      }}
    >
      <label>
        名前
        <input value={formState.name} onChange={(e) => onChange("name", e.target.value)} />
      </label>
      <label>
        メールアドレス
        <input type="email" value={formState.email} onChange={(e) => onChange("email", e.target.value)} />
      </label>
      <label>
        メッセージ
        <textarea value={formState.message} onChange={(e) => onChange("message", e.target.value)} />
      </label>
      <button disabled={isEmpty}>送信</button>
    </form>
  );
}
```

### 解説

#### 型定義

```tsx
onChange: (key: keyof ContactFormValues, value: string) => void;
```

`keyof ContactFormValues` は `"name" | "email" | "message"` という型になります。これで `onChange("nmae", ...)` のようなタイプミスをコンパイル時に見つけられます。入力欄が3つあっても、ハンドラは1つで済みます。

#### `isEmpty` は state にしない

```tsx
const isEmpty = Object.values(formState).some((v) => v.trim() === "");
```

- `Object.values(formState)` で `[name, email, message]` の配列を取り出し、`.some(...)` で「1つでも空のものがあるか」を調べます。
- `trim()` で前後の空白を取り除くので、スペースだけの入力も「空」とみなします。

ここで大事なのは、**`isEmpty` を `useState` で管理していない**ことです。`isEmpty` は `formState` から計算で求められるので、描画のたびに計算すれば十分です。初学者は `useState` と `useEffect` を使って `isEmpty` を別に管理しがちですが、そうすると「`formState` と `isEmpty` の値がずれる」というバグの元になります。**他の値から計算できるものは state にしない**、と覚えておきましょう。

#### 送信処理

```tsx
onSubmit={(e) => {
  e.preventDefault();
  if (!isEmpty) onSubmit(formState);
}}
```

- `e.preventDefault()`: ブラウザは `<form>` が送信されると、標準の動作としてページを再読み込みします。それを止めて、React 側で処理するために呼びます。
- `if (!isEmpty)`: ボタンが無効ならEnterキーでも送信されないのがHTMLの仕様です。それでも念のため確認しておくと、この関数だけで正しさが保証されます。
- `<button>` ではなく `<form>` の `onSubmit` に処理を書いているので、ボタンのクリックでもEnterキーでも同じ処理が動きます。

#### 制御された入力欄（controlled component）

```tsx
<input value={formState.name} onChange={(e) => onChange("name", e.target.value)} />
```

- `value` に props の値を渡しているので、入力欄に表示される内容は**常に `formState` と同じ**になります。これを「制御されたコンポーネント（controlled component）」と呼びます。
- `onChange` がないと、Reactは「読み取り専用の入力欄」として扱い、何を入力しても表示が変わりません（コンソールに警告も出ます）。`value` と `onChange` は必ずセットで書きます。
- `e.target.value` には「入力後の新しい文字列全体」が入っています。

#### `<textarea>` の書き方

HTMLでは `<textarea>中身</textarea>` のようにタグの間に値を書きますが、Reactでは `<input>` と同じく `value` 属性で値を渡します。

#### `<label>` で囲む

`<label>` の中に入力欄を入れると、ラベルの文字をクリックしても入力欄にフォーカスが移ります。`htmlFor` と `id` で関連付けるのと同じ効果を、短く書けます。

## App.tsx

```tsx
import { useState } from "react";
import { ContactForm, type ContactFormValues } from "./ContactForm";

const initialValues: ContactFormValues = { name: "", email: "", message: "" };

export default function App() {
  const [formState, setFormState] = useState(initialValues);

  return (
    <ContactForm
      formState={formState}
      onChange={(key, value) => setFormState((prev) => ({ ...prev, [key]: value }))}
      onSubmit={(values) => {
        console.log(values);
        setFormState(initialValues);
      }}
    />
  );
}
```

### 解説

#### 初期値をコンポーネントの外に置く

```tsx
const initialValues: ContactFormValues = { name: "", email: "", message: "" };
```

初期値は「最初の表示」と「送信後のリセット」の2か所で使います。1か所に定義しておけば、フィールドを増やしたときも修正は1か所で済みます。コンポーネントの外に置いているので、描画のたびに新しいオブジェクトが作られることもありません。

#### 値の更新

```tsx
setFormState((prev) => ({ ...prev, [key]: value }))
```

- `...prev`: 今の値をすべてコピーします。
- `[key]: value`: 変更されたフィールドだけを上書きします。`key` が `"email"` なら `email: value` と同じ意味です（computed property name）。
- `(prev) => ...`: 関数形式で書くと、React が「最新の state」を `prev` に入れてくれます。短い時間に何回も更新しても、古い値をもとに計算してしまう心配がありません。

**やってはいけない書き方**:

```tsx
formState[key] = value;   // 元のオブジェクトを直接書き換えている
setFormState(formState);  // 同じオブジェクトを渡している
```

React は「前と同じオブジェクトかどうか」で変更を判断します。同じオブジェクトを書き換えて渡しても、変更がないとみなされて再描画されません。state は**書き換えずに、新しいオブジェクトを作って渡す**のが基本です。

#### 送信とリセット

```tsx
onSubmit={(values) => {
  console.log(values);
  setFormState(initialValues);
}}
```

state を初期値に戻すだけで、画面の入力欄も空になります。入力欄は `value={formState.xxx}` で state と結びついているからです。これが制御されたコンポーネントの利点で、入力欄を1つずつ空にする処理は必要ありません。

## 1文字入力したときに起きること

名前欄に「山」と入力した場合の流れです。

1. ユーザーが名前欄に「山」と入力する
2. `<input>` の `onChange` が呼ばれ、`onChange("name", "山")` が実行される
3. `App` の `setFormState` が呼ばれ、`formState` が `{ name: "山", email: "", message: "" }` に更新される
4. state が変わったので `App` が再描画され、新しい `formState` が `ContactForm` に渡される
5. `ContactForm` が再描画され、名前欄に「山」が表示される。`isEmpty` もこのとき計算し直される

入力欄に文字が表示されるのは、**state が更新されて再描画された結果**です。入力欄が自分で文字を表示しているわけではありません。

## 要件との対応

| 要件 | 実装箇所 |
| --- | --- |
| 名前・メール・メッセージを制御する | 各入力欄の `value={formState.xxx}` |
| 親の `formState` を表示し、`onChange` で通知 | `ContactForm` は state を持たず、props だけで描画 |
| 送信時に `onSubmit` へ値を渡す | `<form onSubmit>` から `onSubmit(formState)` |
| 空欄があれば送信ボタンを無効化 | `disabled={isEmpty}` |
| 送信後にリセット | 親の `onSubmit` 内で `setFormState(initialValues)` |

## 短くするために使っているポイント

- **`<label>` で入力欄を囲む**: `htmlFor` と `id` を書かなくても、ラベルと入力欄が関連付けられます。
- **`<button>` の `type` を省略**: `<form>` 内の `<button>` は、何も指定しなければ `type="submit"` として動きます。
- **イベントハンドラをインラインで書く**: `onSubmit={(e) => ...}` と書けば `e` の型は推論されるので、型を import する必要がありません。
  - 補足: `@types/react` 19.2 では `React.FormEvent` が非推奨です。ハンドラを別の関数に切り出す場合は `SubmitEvent<HTMLFormElement>` を使います。
- **`useState(initialValues)` の型推論**: 初期値から `ContactFormValues` 型が推論されるので、`useState<ContactFormValues>` と書かなくて済みます。
- **型は `ContactForm.tsx` 側で定義**: フォームの値の型は、それを使うコンポーネントが持ち、`App` が import します。
- **`Object.values(...).some(...)`**: フィールドがすべて文字列なので、この書き方で十分です。文字列以外のフィールドを追加するときは、1つずつ書く形に変えます。

## 最小実装から外したもの

- スタイル（`CSSProperties` の定義）
- 送信結果の画面表示（`console.log` で代用）。表示したい場合は `useState<ContactFormValues | null>(null)` を追加し、`submitted && ...` で条件付き表示にします。
- `required` 属性（ボタンの無効化と役割が重なるため）
