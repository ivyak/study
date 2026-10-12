// Epic GamesのAPIから無料ゲームを取得する関数
async function fetchFreeGames() {
  const url = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=ja&country=JP&allowCountries=JP';
  try {
    const res = await fetch(url);
    const json = await res.json();
    const elements = json.data.Catalog.searchStore.elements;
    
    // 現在無料配布中のものを抽出
    return elements.filter(game => {
      const promos = game.promotions?.promotionalOffers?.[0]?.promotionalOffers || [];
      return promos.some(offer => offer.discountSetting.discountPercentage === 0);
    });
  } catch (error) {
    console.error("データの取得に失敗しました:", error);
    return [];
  }
}

// 起動時にチェックして通知する処理
chrome.runtime.onStartup.addListener(checkAndNotify);
chrome.runtime.onInstalled.addListener(checkAndNotify); // インストール直後も実行

async function checkAndNotify() {
  const games = await fetchFreeGames();
  if (games.length === 0) return; // 何もなければスルー

  chrome.storage.local.get(['notifiedGames'], (result) => {
    const notified = result.notifiedGames || [];
    const newGames = games.filter(g => !notified.includes(g.title));

    if (newGames.length > 0) {
      // 新しい無料ゲームがあればOSの通知を出す
      chrome.notifications.create('epic-free-games', {
        type: 'basic',
        iconUrl: 'icon.png',
        title: 'Epic Games 無料配布更新！',
        message: `${newGames.map(g => g.title).join(', ')} が無料配布中です！クリックしてストアを開きます。`
      });

      // 通知済みのゲームとして保存（次回起動時に重複通知しないため）
      const currentTitles = games.map(g => g.title);
      chrome.storage.local.set({ notifiedGames: currentTitles });
    }
  });
}

// 通知がクリックされたらストアページを開く
chrome.notifications.onClicked.addListener((notificationId) => {
  if (notificationId === 'epic-free-games') {
    // 個別のゲームURLは構造が変わりやすいため、無料ゲーム一覧ページを開くのが一番確実です
    chrome.tabs.create({ url: 'https://store.epicgames.com/ja/free-games' });
    chrome.notifications.clear(notificationId);
  }
});