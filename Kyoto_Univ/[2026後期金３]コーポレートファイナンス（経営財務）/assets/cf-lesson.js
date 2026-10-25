
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
const fmt=(n,d=0)=>n.toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
if(document.getElementById('loan-rate')){
 const input=document.getElementById('loan-rate');
 function calc(){const r=Number(input.value)/100,p=Array.from({length:5},(_,i)=>50/(1+r)**(i+1)).reduce((a,b)=>a+b,0);let bad=p,good=p;for(let t=0;t<5;t++){bad=bad*1.03-50;good=good*(1+r)-50;}document.getElementById('loan-result').innerHTML=`<p class="result">借入額 ${fmt(p,3)} <small>万円</small></p><p>最終残高：元の式 <strong>${fmt(Math.abs(bad)<1e-8?0:bad,3)}万円</strong> ／ 修正式 <strong>${fmt(Math.abs(good)<1e-8?0:good,3)}万円</strong></p>`;}
 input.addEventListener('change',calc);calc();
}
if(document.getElementById('bond-yield')){
 const input=document.getElementById('bond-yield'),price=y=>Array.from({length:5},(_,i)=>(i===4?1050000:50000)/(1+y)**(i+1)).reduce((a,b)=>a+b,0);
 function calc(){let y=Number(input.value)/100,p=price(y);document.getElementById('yield-label').textContent=fmt(y*100,1)+'%';document.getElementById('bond-result').innerHTML=`<p class="result">${fmt(p)} <small>円 · ${y<.05?'プレミアム':y>.05?'ディスカウント':'パー'}</small></p>`;
 const x=n=>48+(n-1)/9*520,yy=n=>170-(n-800000)/400000*140;let pts=[];for(let i=10;i<=100;i++)pts.push(`${x(i/10)},${yy(price(i/1000))}`);
 document.getElementById('bond-chart').innerHTML=`<path d="M48 22 V177 H575" fill="none" stroke="#75684b"/><line x1="48" x2="568" y1="${yy(1000000)}" y2="${yy(1000000)}" stroke="#75684b" stroke-dasharray="4 5"/><polyline points="${pts.join(' ')}" fill="none" stroke="#dfbf73" stroke-width="3"/><circle cx="${x(y*100)}" cy="${yy(p)}" r="6" fill="#fff"/><text x="3" y="31">120万</text><text x="3" y="${yy(1000000)-5}">100万</text><text x="8" y="173">80万</text><text x="46" y="199">1%</text><text x="260" y="199">満期利回り</text><text x="547" y="199">10%</text>`;}
 input.addEventListener('input',calc);calc();
}
if(document.getElementById('reinvest')){
 const b=document.getElementById('reinvest'),r=document.getElementById('equity-rate');
 function calc(){const rein=Number(b.value)/100,rate=Number(r.value)/100,g=.1*rein,d=100*(1-rein),p=d/(rate-g);document.getElementById('reinvest-label').textContent=b.value+'%';document.getElementById('growth-result').innerHTML=`<p>成長率 ${fmt(g*100,1)}% ／ 来期配当 ${fmt(d,1)}</p><p class="result">理論価格 ${fmt(p,2)} <small>／ PBR ${fmt(p/1000,2)}倍</small></p>`;}
 b.addEventListener('input',calc);r.addEventListener('change',calc);calc();
}
