// 【解説：即時実行関数 (IIFE)】
// (function() { ... })(); という構文です。
// この中で宣言された変数（site_idなど）が、他の拡張機能やKULMS自体のプログラムと
// ぶつかってバグを起こさないように、自分だけの「密室（スコープ）」を作るための定石です。
(function() {
    'use strict'; // エラーチェックを厳しくするおまじない。安全なコードを書くために必須です。

    // 【解説：String.prototype.includes()】
    // 文字列の中に特定の文字列が含まれているかを true/false で返します。
    // ここではURLに '/portal' が含まれていない場合（＝LMSの外部ページなど）は処理を止めます。
    if (!window.location.href.includes('/portal')) return;

    // 重複実行の防止（拡張機能が何らかの理由で2回読み込まれた時の対策）
    if (document.getElementById('kulms-ext-container')) return;

    // match() は、JavaScriptで文字列の中から正規表現のパターンに一致する部分を探して、結果を取り出すための関数
    // 結果は配列で返ってくる
    // 基本構文：const 結果 = 探される文字列.match(/検索する正規表現パターン/(フラグ));
    // URLの中から "/portal/site/◯◯◯" の ◯◯◯（site_id）の部分だけを抽出しています。
    // ([^\/]+) は「スラッシュ以外の文字が1文字以上続く部分」をキャプチャ（記憶）するという意味です。
    // window.location.href で現在のページのURL文字列を取得します。
    // 返ってきた配列[0] : マッチした文字列全体　[1], [2]... : キャプチャグループ（正規表現で () で囲んだ部分）があればここに入る
    const urlMatch = window.location.href.match(/\/portal\/site\/([^\/]+)/);

    // 【解説：三項演算子（条件演算子）と startsWith】
    // 構文: 条件 ? 真の場合 : 偽の場合
    // urlMatch[1]（抽出したID）が '~' から始まる場合（個人のマイページ）は null にし、
    // それ以外の正規の授業ページならそのIDを site_id に代入しています。
    const site_id = (urlMatch && !urlMatch[1].startsWith('~')) ? urlMatch[1] : null;

    // 【解説：親コンテナ（マスターコンテナ）の作成】
    // DLボタンと時間割ボタンの両方をまとめるための大枠（箱）を作ります。
    // これをヘッダーに1つだけ挿入することで、レイアウトが崩れにくくなります。
    const masterContainer = document.createElement('div');
    masterContainer.id = 'kulms-ext-container';
    masterContainer.style.position = 'relative';
    masterContainer.style.display = 'inline-flex'; // 横並びにするためのFlexbox
    masterContainer.style.alignItems = 'center';   // 縦方向の中央揃え
    masterContainer.style.height = '100%';
    masterContainer.style.margin = '0 15px';
    masterContainer.style.gap = '8px'; // 中に入るボタン同士の隙間を8pxに設定

    // 排他制御（時間割メニュー用）のために変数を先に準備しておきます。
    let toggleTt = () => {};

    // ==========================================
    // --- 1. 一括DLボタン（全ページ共通で作成） ---
    // ==========================================
    
    // DLボタン用の変数を準備しておきます。
    let toggleMenu = () => {};

    const dlContainer = document.createElement('div');
    dlContainer.style.position = 'relative';
    dlContainer.style.display = 'inline-flex';
    dlContainer.style.height = '100%';
    dlContainer.style.alignItems = 'center'; 

    const mainBtn = document.createElement('button');
    mainBtn.innerHTML = '<span style="margin-right: 5px;">📦</span>資料ダウンロード <span style="font-size: 0.8em; margin-left: 5px;">▼</span>';
    
    Object.assign(mainBtn.style, {
        padding: '6px 15px', backgroundColor: 'rgba(255, 255, 255, 0.15)',
        color: '#ffffff', border: '1px solid rgba(255, 255, 255, 0.5)', borderRadius: '20px',
        cursor: 'pointer', fontWeight: 'bold', fontSize: '14px', display: 'inline-flex',
        alignItems: 'center', transition: 'all 0.2s', height: '32px'
    });

    mainBtn.addEventListener('mouseover', () => mainBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.3)');
    mainBtn.addEventListener('mouseout', () => mainBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.15)');

    const menu = document.createElement('div');
    Object.assign(menu.style, {
        position: 'absolute', top: '100%', right: '0', marginTop: '8px',
        backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
        overflow: 'hidden', minWidth: '220px', zIndex: '10000',
        opacity: '0', visibility: 'hidden', transform: 'translateY(-10px)',
        transition: 'all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1)'
    });

    const createMenuItem = (text, icon, isDisabled = false) => {
        const item = document.createElement('div');
        item.innerHTML = `<span style="margin-right: 8px;">${icon}</span>${text}`;
        Object.assign(item.style, {
            padding: '12px 16px', color: isDisabled ? '#ccc' : '#333', 
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            fontSize: '14px', transition: 'background-color 0.2s',
            borderBottom: '1px solid #eee'
        });
        if (!isDisabled) {
            item.addEventListener('mouseover', () => item.style.backgroundColor = '#f5f5f5');
            item.addEventListener('mouseout', () => item.style.backgroundColor = 'transparent');
        }
        return item;
    };

    const itemAllCourses = createMenuItem('全教科を一括DL', '📚');
    const itemCurrentCourse = createMenuItem('選択中の教科のみDL', '📖', !site_id);
    itemCurrentCourse.style.borderBottom = 'none';

    menu.appendChild(itemAllCourses);
    menu.appendChild(itemCurrentCourse);
    dlContainer.appendChild(mainBtn);
    dlContainer.appendChild(menu);

    let isMenuOpen = false;
    toggleMenu = (forceClose = false) => {
        if (isMenuOpen || forceClose) {
            menu.style.opacity = '0';
            menu.style.visibility = 'hidden';
            menu.style.transform = 'translateY(-10px)';
            isMenuOpen = false;
        } else {
            menu.style.opacity = '1';
            menu.style.visibility = 'visible';
            menu.style.transform = 'translateY(0)';
            isMenuOpen = true;
        }
    };

    mainBtn.addEventListener('click', (e) => { 
        e.stopPropagation(); 
        if (typeof toggleTt === 'function') toggleTt(true);
        toggleMenu(); 
    });
    
    document.addEventListener('click', (e) => { if (!dlContainer.contains(e.target)) toggleMenu(true); });

    async function addFileToZip(zipFolder, url, path) {
        if (!url || typeof url !== 'string') return;
        
        // 学外リンク（YouTube等）の場合は、直接Windowsショートカット(.url)として作成
        if (!url.includes('lms.gakusei.kyoto-u.ac.jp') && url.startsWith('http')) {
            const shortcutContent = `[InternetShortcut]\r\nURL=${url}`;
            if (!path.toLowerCase().endsWith('.url')) path += '.url';
            zipFolder.file(path, shortcutContent);
            return;
        }

        try {
            const res = await fetch(url);
            if (!res.ok) return;
            const blob = await res.blob(); 
            zipFolder.file(path, blob);
        } catch (e) { 
            console.error('DL Error:', url, e); 
            // 取得に失敗した場合も、URLショートカットとして保存して代替する
            const shortcutContent = `[InternetShortcut]\r\nURL=${url}`;
            if (!path.toLowerCase().endsWith('.url')) path += '.url';
            zipFolder.file(path, shortcutContent);
        }
    }

    async function processCourse(zipFolder, targetSiteId) {
        // --- 授業資料の取得 ---
        try {
            const resApiUrl = `https://lms.gakusei.kyoto-u.ac.jp/direct/content/site/${targetSiteId}.json`;
            const resResponse = await fetch(resApiUrl);
            if (resResponse.ok) {
                const resData = await resResponse.json();
                const items = resData.content_collection.filter(i => i.type !== 'collection');
                for (const item of items) {
                    let path = item.title;
                    const m = item.url.match(new RegExp(`/(?:group|attachment)/${targetSiteId}/(.+)$`));
                    if (m) {
                        path = decodeURIComponent(m[1]); 
                    } else {
                        // 外部リンクなどパスが抽出できない場合は、タイトルをファイル名として禁則文字を置換
                        path = path.replace(/[\\/:*?"<>|]/g, '_');
                    }
                    await addFileToZip(zipFolder, item.url, `授業資料/${path}`);
                }
            }
        } catch (e) { console.error(e); }

        // --- 課題リソースの取得 ---
        try {
            const assignApiUrl = `https://lms.gakusei.kyoto-u.ac.jp/direct/assignment/site/${targetSiteId}.json`;
            const assignResponse = await fetch(assignApiUrl);
            if (assignResponse.ok) {
                const assignData = await assignResponse.json();
                const assignments = assignData.assignment_collection || [];
                for (const asgn of assignments) {
                    const title = asgn.title.replace(/[\\/:*?"<>|]/g, '_');
                    const baseDir = `課題資料/${title}`;
                    if (asgn.attachments) {
                        for (const att of asgn.attachments) {
                            await addFileToZip(zipFolder, att.url, `${baseDir}/先生の配布資料/${att.name}`);
                        }
                    }
                    const detailApiUrl = `https://lms.gakusei.kyoto-u.ac.jp/direct/assignment/item/${asgn.id}.json`;
                    const detailRes = await fetch(detailApiUrl);
                    if (detailRes.ok) {
                        const detailData = await detailRes.json();
                        const sub = detailData.submissions ? detailData.submissions[0] : null;
                        if (sub) {
                            if (sub.submittedAttachments) {
                                for (const att of sub.submittedAttachments) {
                                    await addFileToZip(zipFolder, att.url, `${baseDir}/提出したファイル/${att.name}`);
                                }
                            }
                            if (sub.feedbackAttachments) {
                                for (const att of sub.feedbackAttachments) {
                                    await addFileToZip(zipFolder, att.url, `${baseDir}/返却・フィードバック/${att.name}`);
                                }
                            }
                        }
                    }
                }
            }
        } catch (e) { console.error(e); }

        // --- 概要(シラバス)リソースの取得 ---
        try {
            const sylApiUrl = `https://lms.gakusei.kyoto-u.ac.jp/direct/syllabus/site/${targetSiteId}.json`;
            const sylResponse = await fetch(sylApiUrl);
            if (sylResponse.ok) {
                const sylData = await sylResponse.json();
                const syllabuses = sylData.syllabusItem_collection || [];
                for (const syl of syllabuses) {
                    if (syl.attachments) {
                        for (const att of syl.attachments) {
                            await addFileToZip(zipFolder, att.url, `概要/${att.name}`);
                        }
                    }
                }
            }
        } catch(e) { console.error(e); }

        // --- お知らせリソースの取得 ---
        try {
            const annApiUrl = `https://lms.gakusei.kyoto-u.ac.jp/direct/announcement/site/${targetSiteId}.json`;
            const annResponse = await fetch(annApiUrl);
            if (annResponse.ok) {
                const annData = await annResponse.json();
                const announcements = annData.announcement_collection || [];
                for (const ann of announcements) {
                    if (ann.attachments) {
                        const title = ann.title ? ann.title.replace(/[\\/:*?"<>|]/g, '_') : '無題';
                        for (const att of ann.attachments) {
                            await addFileToZip(zipFolder, att.url, `お知らせ/${title}/${att.name}`);
                        }
                    }
                }
            }
        } catch(e) { console.error(e); }
    }

    const startDownload = async (mode) => {
        toggleMenu(true);
        if (mode === 'current' && !site_id) return;

        const originalText = mainBtn.innerHTML;
        mainBtn.innerHTML = '⏳ 準備中...';
        mainBtn.style.pointerEvents = 'none';

        try {
            const zip = new JSZip();

            let targetSites = [];
            let siteDict = {};
            
            // 全教科名を取得する処理
            try {
                const siteRes = await fetch(`https://lms.gakusei.kyoto-u.ac.jp/direct/site.json?_limit=400`);
                if (siteRes.ok) {
                    const siteData = await siteRes.json();
                    (siteData.site_collection || []).forEach(site => {
                        siteDict[site.id] = site.title.replace(/[\\/:*?"<>|]/g, '_');
                        if (mode === 'all' && !site.id.startsWith('~')) {
                            // マイページなどは除外
                            targetSites.push({ id: site.id, name: siteDict[site.id] });
                        }
                    });
                }
            } catch (e) { console.error(e); }

            if (mode === 'current') {
                targetSites = [{ id: site_id, name: siteDict[site_id] || site_id }];
            }

            for (let i = 0; i < targetSites.length; i++) {
                const target = targetSites[i];
                // 進行状況の表示（文字が崩れないように調整）
                mainBtn.innerHTML = `⏳ 処理中 (${i+1}/${targetSites.length})`;
                const folder = mode === 'all' ? zip.folder(target.name) : zip;
                await processCourse(folder, target.id);
            }

            mainBtn.innerHTML = '📦 ZIP圧縮中...';
            const zipBlob = await zip.generateAsync({ type: 'blob' }); 
            
            const downloadUrl = URL.createObjectURL(zipBlob); 
            const a = document.createElement('a'); 
            a.href = downloadUrl;
            
            const downloadName = mode === 'all' ? '全教科一括DL.zip' : `${targetSites[0].name}.zip`;
            a.download = downloadName; 
            a.click(); 
            URL.revokeObjectURL(downloadUrl);

            mainBtn.innerHTML = '✅ 完了！';
            mainBtn.style.backgroundColor = 'rgba(40, 167, 69, 0.8)';

        } catch (error) {
            console.error(error);
            mainBtn.innerHTML = '❌ エラー';
            mainBtn.style.backgroundColor = 'rgba(220, 53, 69, 0.8)';
        } finally {
            setTimeout(() => {
                mainBtn.innerHTML = originalText;
                mainBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.15)';
                mainBtn.style.pointerEvents = 'auto';
            }, 3000);
        }
    };

    itemAllCourses.addEventListener('click', () => startDownload('all'));
    if (site_id) {
        itemCurrentCourse.addEventListener('click', () => startDownload('current'));
    }

    masterContainer.appendChild(dlContainer);


    // ==========================================
    // --- 2. 時間割ボタン（全ページ共通で作成） ---
    // ==========================================
    
    // このブロックは if (site_id) の外にあるため、ダッシュボード等の教科外ページでも必ず実行されます。
    const ttContainer = document.createElement('div');
    ttContainer.style.position = 'relative';
    ttContainer.style.display = 'inline-flex';
    ttContainer.style.alignItems = 'center';
    ttContainer.style.height = '100%';

    const ttBtn = document.createElement('button');
    ttBtn.innerHTML = '<span style="margin-right: 5px;">🗓️</span>時間割';
    Object.assign(ttBtn.style, {
        padding: '6px 15px', backgroundColor: 'rgba(255, 255, 255, 0.15)',
        color: '#ffffff', border: '1px solid rgba(255, 255, 255, 0.5)', borderRadius: '20px',
        cursor: 'pointer', fontWeight: 'bold', fontSize: '14px', display: 'inline-flex',
        alignItems: 'center', transition: 'all 0.2s', height: '32px'
    });
    ttBtn.addEventListener('mouseover', () => ttBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.3)');
    ttBtn.addEventListener('mouseout', () => ttBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.15)');

    const ttMenu = document.createElement('div');
    Object.assign(ttMenu.style, {
        position: 'absolute', top: '100%', right: '0', marginTop: '8px',
        backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
        overflow: 'hidden', width: '450px', zIndex: '10000',
        opacity: '0', visibility: 'hidden', transform: 'translateY(-10px)',
        transition: 'all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1)', padding: '10px'
    });

    ttContainer.appendChild(ttBtn);
    ttContainer.appendChild(ttMenu);
    
    // 時間割コンテナもマスターコンテナに追加します。
    // （教科ページならDLボタンの右に並び、ホームなら時間割ボタンだけが配置されます）
    masterContainer.appendChild(ttContainer);

    // 【解説：getComputedStyle を使った色の抽出】
    // 構文: window.getComputedStyle(要素)
    // HTMLのstyle属性だけでなく、外部CSSファイルなどで最終的に適用されている「実際の見た目」を取得します。
    // 他の拡張機能がどうやって色を塗っていても、最終的な描画色を特定できる強力なハックです。
    function extractExtColor(el) {
        if (!el) return '#ffffff';
        // 'transparent' などの透明色や黒を除外するチェッカー関数
        const checkColor = (c) => c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent' && c !== 'rgb(255, 255, 255)' && c !== '#ffffff';
        
        // 【解説：スプレッド構文 (...) と filter(Boolean)】
        // ...el.querySelectorAll('*') で要素の中にある全ての子要素を配列として展開・結合しています。
        // filter(Boolean) は null や undefined を配列から取り除くためのテクニックです。
        const targets = [el, el.querySelector('a'), ...el.querySelectorAll('*')].filter(Boolean);

        for (let target of targets) {
            const cs = window.getComputedStyle(target);
            // 左側の枠線(border-left)に色がついていれば取得
            if (checkColor(cs.borderLeftColor) && parseInt(cs.borderLeftWidth) > 0) return cs.borderLeftColor;
            // 背景色(background-color)がついていれば取得
            if (checkColor(cs.backgroundColor)) return cs.backgroundColor;

            // ::before などの疑似要素（CSSで作られた装飾）の色もチェック
            for (let pseudo of ['::before', '::after']) {
                const pseudoCs = window.getComputedStyle(target, pseudo);
                if (checkColor(pseudoCs.borderLeftColor) && parseInt(pseudoCs.borderLeftWidth) > 0) return pseudoCs.borderLeftColor;
                if (checkColor(pseudoCs.backgroundColor)) return pseudoCs.backgroundColor;
            }
        }
        return '#ffffff';
    }

    // 教科の「正式名称」をAPIから一括取得し、オブジェクト（辞書）としてキャッシュしておきます。
    // これにより、画面上で「プログラミ...」のように省略されていてもフルネームを復元できます。
    const apiTitles = {};
    fetch('https://lms.gakusei.kyoto-u.ac.jp/direct/site.json?_limit=400')
        .then(r => r.json())
        .then(data => {
            (data.site_collection || []).forEach(site => {
                // 正規表現 /^\[.*?\]\s*/ : 文字列の先頭(^)にある [2026前期...] のカッコ部分を空文字に置換して削除
                apiTitles[site.id] = site.title.replace(/^\[.*?\]\s*/, '').trim();
            });
            // APIの取得が終わる前にユーザーがメニューを開いていた場合は、再描画して最新化します
            let isTtOpenLocal = ttMenu.style.visibility === 'visible';
            if (isTtOpenLocal) buildTimetable();
        }).catch(e => console.error('API Fetch Error:', e));

    // 時間割のDOMを生成するメイン関数
    function buildTimetable() {
        ttMenu.innerHTML = '';
        const classes = {}; // 曜日と時限をキーにして教科データを格納するオブジェクト
        
        // 画面上にある全ての教科リンク（/portal/site/）をかき集めます
        const links = document.querySelectorAll('a[href*="/portal/site/"]');
        
        links.forEach(a => {
            const m = a.href.match(/\/portal\/site\/([a-zA-Z0-9\-\_]+)/);
            if (!m) return;
            const siteId = m[1];
            
            // a.textContentなどでテキストを取得し、改行(\rや\n)を取り除いて1行にします
            let rawText = (a.getAttribute('title') || a.textContent || '').replace(/\r?\n|\r/g, '').trim();
            // 「曜日」と「時限」を抽出
            const match = rawText.match(/\[.*?([月火水木金])\s*([1-6１-６]).*?\]\s*(.*)/);
            
            if (match) {
                const day = match[1];
                
                // 【解説：文字コードによる全角・半角変換】
                // charCodeAt(0)で文字コードを取得。全角の'１'等は255より大きいため、65248を引くことで半角の'1'に変換できます。
                const period = String.fromCharCode(match[2].charCodeAt(0) - (match[2].charCodeAt(0) > 255 ? 65248 : 0));
                
                // APIでキャッシュした正式名称があればそれを使い、なければ抽出した文字から省略記号(…)を消して使います
                const name = apiTitles[siteId] || match[3].replace(/…|\.{3,}$/, '').trim();
                const color = extractExtColor(a.closest('li') || a);
                
                if (!classes[day]) classes[day] = {};
                
                // もし同じ時限に別のリンク（上部タブとサイドバーなど）が重複した場合、色が着いている方を優先保存します
                if (!classes[day][period] || (classes[day][period].color === '#ffffff' && color !== '#ffffff')) {
                    classes[day][period] = { name, url: a.href, color };
                }
            }
        });

        // 【解説：CSS Grid を使った表のレイアウト】
        // display: grid と grid-template-columns を使うと、簡単にエクセルのような表組みができます。
        // 25px(1列目) + 残りの5列は1fr(利用可能なスペースを均等に割る)という意味です。
        const grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = '25px repeat(5, 1fr)';
        grid.style.gap = '3px';
        grid.style.backgroundColor = '#ddd'; // gapの部分から背景色が見えることで「枠線」のように見せます
        grid.style.border = '1px solid #ccc';
        grid.style.borderRadius = '4px';

        const days = ['月', '火', '水', '木', '金'];
        
        // 【解説：Dateオブジェクト】
        // getDay() は 0(日曜日) 〜 6(土曜日) の数値を返すので、それをインデックスにして今日の漢字を取得します。
        const currentDay = ['日', '月', '火', '水', '木', '金', '土'][new Date().getDay()];

        // セル（マス目）を作る共通関数
        const createCell = (text, bg, isHeader) => {
            const div = document.createElement('div');
            div.innerText = text;
            Object.assign(div.style, {
                backgroundColor: bg, padding: '4px', textAlign: 'center',
                fontSize: isHeader ? '12px' : '11px', fontWeight: isHeader ? 'bold' : 'normal',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#333', minHeight: isHeader ? '25px' : '50px'
            });
            return div;
        };

        // 左上の空白セル
        grid.appendChild(createCell('', '#f8f9fa', true));
        
        // 曜日ヘッダーの生成
        days.forEach(d => {
            const isToday = (d === currentDay);
            // 今日なら薄い青色（#d0ebff）にする
            grid.appendChild(createCell(d, isToday ? '#d0ebff' : '#f8f9fa', true));
        });

        // 1限〜5限のループ
        for (let period = 1; period <= 5; period++) {
            grid.appendChild(createCell(period.toString(), '#f8f9fa', true)); // 左端の時限番号セル
            
            days.forEach(day => {
                const info = classes[day] && classes[day][period];
                const isToday = (day === currentDay);
                const emptyBg = isToday ? '#f1f8ff' : '#ffffff'; // 空きコマの背景色

                if (info) {
                    const aTag = document.createElement('a');
                    aTag.href = info.url;
                    aTag.innerText = info.name;
                    aTag.title = info.name; // マウスホバーでツールチップとしてフルネームを表示
                    
                    Object.assign(aTag.style, {
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        backgroundColor: (info.color === '#ffffff' && isToday) ? emptyBg : info.color,
                        color: '#333', fontSize: '11px', textDecoration: 'none', 
                        textAlign: 'center', height: '100%', width: '100%',
                        padding: '4px', boxSizing: 'border-box', lineHeight: '1.3', 
                        wordBreak: 'break-all', position: 'relative'
                    });
                    
                    // 【解説：box-shadow のハック利用】
                    // rgba(255,255,255,0.7) で白い半透明の影を要素の内側(inset)いっぱいに広げることで、
                    // 背景の原色を少し薄く（パステル調に）して文字を読みやすくしています。
                    if(info.color !== '#ffffff') {
                         aTag.style.boxShadow = 'inset 0 0 0 1000px rgba(255,255,255,0.7)';
                         aTag.style.fontWeight = 'bold';
                    }
                    
                    // 【解説：filter: brightness】
                    // マウスが乗った時に少し暗く(0.9倍)して、ボタンっぽさを演出します。
                    aTag.addEventListener('mouseover', () => aTag.style.filter = 'brightness(0.9)');
                    aTag.addEventListener('mouseout', () => aTag.style.filter = 'none');
                    grid.appendChild(aTag);
                } else {
                    grid.appendChild(createCell('', emptyBg, false)); // 教科がない場合は空きコマセルを追加
                }
            });
        }
        ttMenu.appendChild(grid);
        
        // 【解説：Object.keys(obj).length】
        // オブジェクトの中にプロパティ（キー）がいくつあるかを数えます。
        // apiTitles が空＝まだAPIの取得が終わっていない場合は、ローディング文字を出します。
        if (Object.keys(apiTitles).length === 0) {
            const loadingInd = document.createElement('div');
            Object.assign(loadingInd.style, { fontSize: '10px', color: '#888', textAlign: 'right', marginTop: '5px' });
            loadingInd.innerText = '⏳ 詳細名をAPIから取得中...';
            ttMenu.appendChild(loadingInd);
        }
    }

    let isTtOpen = false;
    toggleTt = (forceClose = false) => {
        if (isTtOpen || forceClose) {
            ttMenu.style.opacity = '0';
            ttMenu.style.visibility = 'hidden';
            ttMenu.style.transform = 'translateY(-10px)';
            isTtOpen = false;
        } else {
            // メニューが開く直前に常に最新情報を読み取ってDOM(表)を再構築します
            buildTimetable();
            ttMenu.style.opacity = '1';
            ttMenu.style.visibility = 'visible';
            ttMenu.style.transform = 'translateY(0)';
            isTtOpen = true;
        }
    };

    ttBtn.addEventListener('click', (e) => { 
        e.stopPropagation(); 
        if (typeof toggleMenu === 'function') toggleMenu(true); // DLメニューが開いていれば強制的に閉じる（排他制御）
        toggleTt(); 
    });
    // どこか外側をクリックした時に閉じるイベント
    document.addEventListener('click', (e) => { if (!ttContainer.contains(e.target)) toggleTt(true); });


    // ==========================================
    // --- 3. ヘッダーへの挿入 ---
    // ==========================================
    const insertButton = () => {
        // すでに親箱が挿入されていれば何もしない
        if (document.body.contains(masterContainer)) return;

        // 【解説：querySelector】
        // CSSセレクタを使って、画面上の特定のHTML要素を探し出します。
        // KULMSの仕様変更に備えて、複数の候補（selectors）を用意して順番に探しています。
        const selectors = [
            '#mastLogin > ul', '.Mrphs-loginNav > ul', 'ul.nav[role="menubar"]', 
            'nav[aria-label="ユーザーナビゲーション"] ul', 'nav[aria-label="User navigation"] ul', 'header .navbar-right'
        ];

        let targetNav = null;
        for (const selector of selectors) {
            targetNav = document.querySelector(selector);
            if (targetNav) break; // 見つかったらループを抜ける
        }

        if (targetNav) {
            const li = document.createElement('li');
            li.style.display = 'inline-flex';
            li.style.alignItems = 'center';  
            li.style.height = '100%';        
            li.style.listStyle = 'none';
            li.appendChild(masterContainer); // 親箱ごと一気に挿入
            
            // 見つけたリストの一番最初（ヘルプアイコン等の左隣）に挿入する
            targetNav.insertBefore(li, targetNav.firstChild);
        } else {
            // 見つからなかった場合の保険的配置処理（絶対位置指定）
            const header = document.querySelector('header') || document.querySelector('#masthead');
            if (header) {
                if (window.getComputedStyle(header).position === 'static') header.style.position = 'relative';
                masterContainer.style.position = 'absolute';
                masterContainer.style.right = '320px';
                // top: 0 と bottom: 0 を両方指定することで、ヘッダーの高さにぴったり追従させます
                masterContainer.style.top = '0';
                masterContainer.style.bottom = '0';
                header.appendChild(masterContainer);
            } else {
                // 最終手段として画面の右下に固定表示
                masterContainer.style.position = 'fixed';
                masterContainer.style.bottom = '30px';
                masterContainer.style.right = '30px';
                masterContainer.style.zIndex = '9999';
                document.body.appendChild(masterContainer);
            }
        }
    };

    // 【解説：setInterval による定期実行】
    // 構文: setInterval(関数, ミリ秒)
    // 画面の描画が遅い場合に対応するため、0.5秒おきに「ヘッダーはできた？」と確認しにいきます。
    // 無限ループにならないよう、10回（5秒）試したら諦める（clearInterval）仕組みを入れています。
    let attempts = 0;
    const tryInsert = setInterval(() => {
        attempts++;
        if (document.querySelector('header') || document.querySelector('#mastLogin') || document.body) {
            insertButton();
            if (document.body.contains(masterContainer)) clearInterval(tryInsert);
        }
        if (attempts >= 10) clearInterval(tryInsert);
    }, 500);

})();