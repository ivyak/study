document.addEventListener('DOMContentLoaded', async () => {
  const content = document.getElementById('content');
  
  try {
    // APIを直接叩く
    const url = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=ja&country=JP&allowCountries=JP';
    const res = await fetch(url);
    const json = await res.json();
    const elements = json.data.Catalog.searchStore.elements;
    
    const freeGames = elements.filter(game => {
      const promos = game.promotions?.promotionalOffers?.[0]?.promotionalOffers || [];
      return promos.some(offer => offer.discountSetting.discountPercentage === 0);
    });

    if (freeGames.length === 0) {
      // ❗️無料ゲームがない場合は、わざわざ通知せずにここでテキスト表示
      content.innerHTML = '<p style="text-align:center;">現在無料配布中のゲームはありません🎮</p>';
      return;
    }

    // 無料ゲームがある場合はストアへ飛ぶボタンを生成
    content.innerHTML = '';
    freeGames.forEach(game => {
      const btn = document.createElement('button');
      btn.className = 'game-btn';
      btn.textContent = `${game.title} を開く`;
      btn.onclick = () => {
        chrome.tabs.create({ url: 'https://store.epicgames.com/ja/free-games' });
      };
      content.appendChild(btn);
    });

  } catch (error) {
    content.innerHTML = '<p style="color:red;">エラーが発生しました</p>';
  }
});