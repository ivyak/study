
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
document.querySelectorAll('details').forEach(d=>{
 const s=d.querySelector('summary'); let anim=null;
 s.addEventListener('click',e=>{
  if(reduced.matches||!d.animate)return;
  e.preventDefault();if(anim)return;
  const closing=d.open,from=d.getBoundingClientRect().height;
  if(!closing)d.open=true;
  const to=closing?s.getBoundingClientRect().height+1:d.getBoundingClientRect().height;
  d.style.overflow='hidden';
  anim=d.animate({height:[from+'px',to+'px']},{duration:260,easing:'ease-in-out'});
  anim.onfinish=()=>{if(closing)d.open=false;d.style.overflow='';anim=null;};
 });
});
const menu=document.querySelector('.legacy-page .menu-button'),side=document.querySelector('.legacy-page .sidebar');
function closeMenu(focus=false){side.classList.remove('open');menu.setAttribute('aria-expanded','false');if(focus)menu.focus();}
menu.addEventListener('click',()=>{const open=side.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));if(open)side.querySelector('a').focus();});
side.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>closeMenu()));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&side.classList.contains('open'))closeMenu(true);});
document.addEventListener('click',e=>{if(!side.contains(e.target)&&!menu.contains(e.target))closeMenu();});
const navLinks=[...document.querySelectorAll('.toc a')];
const sections=[...document.querySelectorAll('.legacy-page main section')];
function updateToc(){let current=sections[0];for(const s of sections)if(s.getBoundingClientRect().top<150)current=s;navLinks.forEach(a=>{if(a.hash==='#'+current.id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}
addEventListener('scroll',updateToc,{passive:true});updateToc();

const elapsed=document.querySelector('#elapsed'),confidence=document.querySelector('#confidence'),result=document.querySelector('#interval-result');
function calculate(){const x=elapsed.valueAsNumber,c=Number(confidence.value),a=(1-c)/2; if(!Number.isFinite(x)||x<=0){result.textContent='経過年数に正の数を入力してください。';return;} const fmt=n=>n.toLocaleString('ja-JP',{maximumFractionDigits:2,minimumFractionDigits:2});result.innerHTML=`<p>両端に除く割合：各 ${((1-c)*50).toFixed(1)}%</p><p>総存続期間 θ：<strong>${fmt(x/(1-a))} ～ ${fmt(x/a)} 年</strong></p><p class="result">残り期間：${fmt(x*a/(1-a))} ～ ${fmt(x*(1-a)/a)} 年</p><p class="quiet">小数第2位まで表示。一様な訪問時点という講義のモデルの下での区間です。</p>`;}
elapsed.addEventListener('input',calculate);confidence.addEventListener('change',calculate);calculate();
