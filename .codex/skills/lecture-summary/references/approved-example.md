# 承認済み完成例：公共政策論II 第2回

ユーザーが理想的と評価した本文と一覧の保存版。HTML断片は文章の量・構成・一覧の密度を確認するための参照であり、独立した表示用ファイルではない。

基準ページ（リポジトリルートから）：`Kyoto_Univ/[2026後期金２]公共政策論II/第2回_条件付確率とベイズ推論_要約.html`。UIには現行の共通UIを使う。

本文は短い段落と代表例で要点をつなぎ、一覧は名前と式・用語と意味だけ。科目名、具体例、節数、項目数は次回の資料に合わせる。

```html
<section id="conditional"><h2>1. 「何が分かっているか」で確率は変わる</h2>
<p>「虐待する夫が妻を殺す確率」と「虐待されていた妻が殺されたとき、夫が犯人である確率」は別のもの。後者では、<strong>すでに殺された場合だけに対象を絞る</strong>ため、分母が変わる。</p>
<p>これが<strong>条件付確率</strong>。P(A | B) は「Bが分かっているときのAの確率」で、P(B | A)とは一般に一致しない。</p>
<p class="source">p.1〜15</p></section>
<section id="bayes"><h2>2. 結果から原因を考えるのがベイズ推論</h2>
<p>黒いアメを見て「どのビンから取ったか」を考えるには、各ビンの<strong>選ばれやすさ（事前確率）</strong>と、そこから<strong>黒アメが出る確率（尤度）</strong>の両方が必要になる。</p>
<div class="equation">結果を見たあとの候補の確率（事後確率）<br>＝ その候補の「事前確率 × 尤度」<br>÷ 全候補の「事前確率 × 尤度」の合計</div>
<p>結果の出やすさだけで判断せず、<strong>その原因がもともとどれくらいありそうか</strong>も考慮する。</p>
<p class="source">p.16〜35、50〜52</p></section>
<section id="screening"><h2>3. 「99%の検査」でも、陽性後は約23%</h2>
<p>講義では、感染割合0.3%、感染者が陽性になる確率99%、非感染者が誤って陽性になる確率1%とする。10万人で考えると、陽性になるのは次の人数。</p>
<div class="takeaways"><p>感染者300人のうち → <strong>297人</strong><br>非感染者99,700人のうち → <strong>997人</strong></p></div>
<p>したがって、陽性者のうち本当に感染している割合は、<strong>297 ÷ (297 + 997) ≈ 23%</strong>。感染者が少ない集団では、大勢の非感染者から出る偽陽性が多くなる。</p>
<p class="note">数値は講義上の設定であり、現在の実際の検査性能や個人の診断を表すものではない。</p>
<p class="source">p.36〜49 · 人数・割合は資料に基づく計算</p></section>
<section id="takeaway"><h2>覚えておくこと</h2><p><strong>確率を読むときは「何を条件に、誰を分母にしているか」を確認する。</strong>結果から原因を推測するときは、事前確率も忘れない。</p></section>
<section id="reference"><h2>公式・定理・定義・用語一覧</h2><h3>名前と式</h3><div class="table-wrap"><table><thead><tr><th scope="col">名前</th><th scope="col">式</th></tr></thead><tbody><tr><th scope="row">条件付確率</th><td>P(B | A) = P(A ∩ B) / P(A)　［P(A) &gt; 0］</td></tr><tr><th scope="row">確率の乗法公式</th><td>P(A ∩ B) = P(A)P(B | A) = P(B)P(A | B)　［P(A), P(B) &gt; 0］</td></tr><tr><th scope="row">独立・独立事象の乗法公式</th><td>P(A ∩ B) = P(A)P(B)<br>P(B | A) = P(B)　［P(A) &gt; 0］</td></tr><tr><th scope="row">ベイズの定理（ベイズの公式・逆確率の公式）</th><td>P(A | F) = P(F | A)P(A) / P(F)　［P(A), P(F) &gt; 0］</td></tr><tr><th scope="row">分割</th><td>A ∩ B = B ∩ C = C ∩ A = ∅<br>A ∪ B ∪ C = Ω</td></tr><tr><th scope="row">全確率の法則</th><td>P(F) = P(F ∩ A) + P(F ∩ B) + P(F ∩ C)<br>= P(F | A)P(A) + P(F | B)P(B) + P(F | C)P(C)<br>［A・B・C は分割、P(A), P(B), P(C) &gt; 0］</td></tr><tr><th scope="row">ベイズの公式の展開形</th><td>P(C | F) = P(F | C)P(C)<br>÷ {P(F | A)P(A) + P(F | B)P(B) + P(F | C)P(C)}<br>［A・B・C は分割、P(A), P(B), P(C), P(F) &gt; 0］</td></tr><tr><th scope="row">相対度数</th><td>事象が起こった回数 / 観測回数</td></tr><tr><th scope="row">陽性者のうち感染している割合</th><td>真の感染者で陽性の人数 / 陽性者全体の人数</td></tr><tr><th scope="row">確率の範囲</th><td>0 ≤ P(A) ≤ 1</td></tr><tr><th scope="row">確実な事象の確率</th><td>P(Ω) = 1</td></tr><tr><th scope="row">不可能な事象の確率</th><td>P(∅) = 0</td></tr><tr><th scope="row">排反な事象の加法性</th><td>P(A₁ ∪ ⋯ ∪ Aₙ) = P(A₁) + ⋯ + P(Aₙ)<br>［i ≠ j なら Aᵢ ∩ Aⱼ = ∅］</td></tr></tbody></table></div><h3>用語と意味</h3><div class="table-wrap"><table><thead><tr><th scope="col">用語</th><th scope="col">意味</th></tr></thead><tbody><tr><th scope="row">事象</th><td>起こるかどうかを考える出来事。</td></tr><tr><th scope="row">A ∩ B ／ A ∪ B</th><td>「AかつB」／「AまたはB」。</td></tr><tr><th scope="row">Ω ／ ∅</th><td>すべての場合（全事象）／不可能な事象（空事象）。</td></tr><tr><th scope="row">条件付確率 P(B | A)</th><td>A が起きたという条件のもとで B が起きる確率。資料の Pr(B if A) と同じ。</td></tr><tr><th scope="row">独立 ／ 従属</th><td>一方の事象が起きても他方の確率が変わらないこと／独立でないこと。</td></tr><tr><th scope="row">逆推理</th><td>得られた結果から、それに至った原因や過程を推測すること。</td></tr><tr><th scope="row">条件事象</th><td>別の事象の確率を考える際の条件となる事象。</td></tr><tr><th scope="row">事前確率 P(A)</th><td>結果 F を知る前の、候補 A の確率。</td></tr><tr><th scope="row">尤度 P(F | A)</th><td>候補 A を仮定したとき、観測した結果 F が出る確率。</td></tr><tr><th scope="row">事後確率 P(A | F)</th><td>結果 F を知ったあとの、候補 A の確率。</td></tr><tr><th scope="row">分割（partition）</th><td>互いに重ならない事象で、全体を尽くすこと。</td></tr><tr><th scope="row">統計的確率</th><td>同じ条件で観測を十分多く繰り返したときの相対度数によって捉える確率。</td></tr><tr><th scope="row">prevalence（資料では「罹患率」）</th><td>対象集団のうち感染している人の割合。</td></tr><tr><th scope="row">偽陽性</th><td>本当は非感染なのに、検査で陽性と判定されること。</td></tr></tbody></table></div></section>

```
