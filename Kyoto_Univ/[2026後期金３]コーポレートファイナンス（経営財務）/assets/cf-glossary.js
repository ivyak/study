const metricViews = {
  roe: {marks: ['equity','net'], title:'ROE = 75.6 ÷ 500 = 15.12%', text:'分子：株主に帰属する純利益 ／ 分母：平均自己資本。株主資本コストと対応。'},
  roa: {marks: ['assets','net'], title:'純利益ROA = 75.6 ÷ 1,000 = 7.56%', text:'分子：純利益 ／ 分母：平均総資産。余剰現金を含む資産全体で割る。この図は純利益ROAを採用。'},
  roic:{marks:['operating','payable','nopat'],title:'ROIC = 84 ÷ (900 − 200) = 12.00%',text:'分子：NOPAT ／ 分母：平均事業資産900から営業負債200を控除した投下資本700。余剰現金100を除く定義。図の買掛金は分母から引く項目。'},
  roi: {marks:[],title:'別の案件：ROI = (120 − 100) ÷ 100 = 20%',text:'特定の投資の利益と元手を対応させる一般的な率。下の別案件を参照。企業全体のBS・PLの特定項目に一意には結び付かない。'}
};
function setMetric(key) {
 const view=metricViews[key];
 document.querySelectorAll('[data-metric]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.metric===key)));
 document.querySelectorAll('[data-mark]').forEach(e=>{
  const marks=e.dataset.mark.split(' '),active=marks.some(m=>view.marks.includes(m));
  e.classList.toggle('metric-active',active);
  e.classList.toggle('metric-subtract',active&&marks.includes('payable'));
 });
 const result=document.getElementById('metric-result');result.replaceChildren();
 const title=document.createElement('b'),text=document.createElement('p');title.textContent=view.title;text.textContent=view.text;result.append(title,text);
 document.getElementById('project-card').classList.toggle('metric-active',key==='roi');
}
document.querySelectorAll('[data-metric]').forEach(b=>b.addEventListener('click',()=>setMetric(b.dataset.metric)));
if(document.getElementById('metric-result')) setMetric('roe');
const equityInput=document.getElementById('wacc-equity'),debtInput=document.getElementById('wacc-debt');
function updateWacc(){
 const re=Number(equityInput.value)/100,rd=Number(debtInput.value)/100,wacc=800/1100*re+300/1100*rd*.7;
 document.getElementById('wacc-equity-label').textContent=(re*100).toFixed(1)+'%';document.getElementById('wacc-debt-label').textContent=(rd*100).toFixed(1)+'%';
 document.getElementById('wacc-result').innerHTML=`<p class="result">WACC ${(wacc*100).toFixed(2)}%</p><p>ROIC 12%との差：${((.12-wacc)*100).toFixed(2)}パーセントポイント</p>`;
}
if(equityInput && debtInput){equityInput.addEventListener('input',updateWacc);debtInput.addEventListener('input',updateWacc);updateWacc();}
// Both navigation rows retain their current item on small screens.
for(const nav of document.querySelectorAll('.tabs,.subtabs')){
 const current=nav.querySelector('[aria-current]');
 if(current) nav.scrollLeft=Math.max(0,current.offsetLeft-nav.offsetLeft-nav.clientWidth/2+current.clientWidth/2);
}
const termSearch=document.getElementById('term-search');
if(termSearch){
 const rows=[...document.querySelectorAll('[data-dictionary-row]')];
 termSearch.addEventListener('input',()=>{
  const query=termSearch.value.trim().toLocaleLowerCase();let count=0;
  for(const row of rows){row.hidden=!row.textContent.toLocaleLowerCase().includes(query);if(!row.hidden)count++;}
  document.getElementById('term-search-count').textContent=`${count} / ${rows.length}語`;
 });
}
function revealHash(){
 let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
 if(!id)return;const target=document.getElementById(id);if(!target)return;
 let parent=target.parentElement,opened=false;
 while(parent){if(parent.tagName==='DETAILS'&&!parent.open){parent.open=true;opened=true;}parent=parent.parentElement;}
 if(target.matches('[data-dictionary-row]')&&termSearch){termSearch.value='';termSearch.dispatchEvent(new Event('input'));}
 if(opened)requestAnimationFrame(()=>target.scrollIntoView({block:'start'}));
}
addEventListener('hashchange',revealHash);revealHash();
const capmInputs=['capm-rf','capm-erp','capm-beta'].map(id=>document.getElementById(id));
if(capmInputs.every(Boolean)){
 function capm(){
  const output=document.getElementById('capm-result');
  if(capmInputs.some(e=>!e.validity.valid||e.value==='')){output.textContent='各入力欄に範囲内の数値を入れてください。';return;}
  const [rf,erp,beta]=capmInputs.map(e=>Number(e.value));
  output.innerHTML=`<p class="result">株主資本コスト rₑ = ${(rf+beta*erp).toFixed(2)}%</p><p>時間の対価 ${rf.toFixed(2)}% ＋ 市場リスクへの上乗せ ${(beta*erp).toFixed(2)}パーセントポイント</p>`;
 }
 capmInputs.forEach(e=>e.addEventListener('input',capm));capm();
}
const ddmInputs=['ddm-dividend','ddm-rate','ddm-growth'].map(id=>document.getElementById(id));
if(ddmInputs.every(Boolean)){
 function ddm(){
  const output=document.getElementById('ddm-result');
  if(ddmInputs.some(e=>!e.validity.valid||e.value==='')){output.textContent='各入力欄に範囲内の数値を入れてください。';return;}
  const [d,rate,growth]=ddmInputs.map(e=>Number(e.value));
  if(rate<=growth){output.innerHTML='<p class="result">この式は使えません：rₑ &gt; g が必要です。</p>';return;}
  const price=d/((rate-growth)/100);
  output.innerHTML=`<p class="result">理論株価 ${price.toLocaleString('ja-JP',{minimumFractionDigits:2,maximumFractionDigits:2})} 円</p><p>分母 rₑ−g = ${(rate-growth).toFixed(2)}パーセントポイント（小数では ${((rate-growth)/100).toFixed(4)}）</p>`;
 }
 ddmInputs.forEach(e=>e.addEventListener('input',ddm));ddm();
}
const lectureTabs=document.querySelector('.tabs');
if(lectureTabs){
 const sizeNav=()=>document.documentElement.style.setProperty('--lecture-tabs-height',lectureTabs.getBoundingClientRect().height+'px');
 sizeNav();if(typeof ResizeObserver!=='undefined')new ResizeObserver(sizeNav).observe(lectureTabs);else addEventListener('resize',sizeNav);
}
