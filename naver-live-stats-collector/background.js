const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function notify(text, options = {}) {
  chrome.runtime.sendMessage({ type: "COLLECTION_PROGRESS", text, ...options }).catch(() => {});
}

function waitForTab(tabId) {
  return new Promise((resolve) => {
    const listener = (updatedId, changeInfo) => {
      if (updatedId === tabId && changeInfo.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function messageTab(tabId, message, retries = 20) {
  let lastError;
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const response = await chrome.tabs.sendMessage(tabId, message);
      if (!response?.ok) throw new Error(response?.error || "페이지에서 값을 읽지 못했습니다.");
      return response.data;
    } catch (error) {
      lastError = error;
      await sleep(300);
    }
  }
  throw lastError;
}

function csvText(rows) {
  const columns = ["계정", "방송 ID", "방송 제목", "방송일시", "라이브중 시청수", "유니크 결제자수", "결제 상품수", "데이터 업데이트 시각"];
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return `\ufeff${columns.map(quote).join(",")}\r\n${rows.map((row) => columns.map((column) => quote(row[column])).join(",")).join("\r\n")}`;
}

async function collect(expectedStore) {
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!activeTab?.id || !activeTab.url?.includes("sell.smartstore.naver.com/l/v1/broadcasts")) {
    throw new Error("날짜 조회를 마친 쇼핑라이브 라이브 목록 탭에서 실행해주세요.");
  }
  const originalUrl = activeTab.url;
  const broadcasts = await messageTab(activeTab.id, { type: "COLLECT_LIST" });
  const results = [];
  try {
    for (let index = 0; index < broadcasts.length; index += 1) {
      const item = broadcasts[index];
      notify(`${index + 1}/${broadcasts.length} · ${item.broadcastAt} 통계 확인 중…`);
      const loaded = waitForTab(activeTab.id);
      await chrome.tabs.update(activeTab.id, { url: item.statsUrl });
      await loaded;
      const stat = await messageTab(activeTab.id, { type: "EXTRACT_STATS", expectedStore, item });
      results.push(stat);
    }
  } finally {
    await chrome.tabs.update(activeTab.id, { url: originalUrl });
  }
  const firstDate = broadcasts[0].broadcastAt.slice(0, 10).replaceAll("-", "");
  const dataUrl = `data:text/csv;charset=utf-8,${encodeURIComponent(csvText(results))}`;
  await chrome.downloads.download({ url: dataUrl, filename: `naver_live_stats_${firstDate}.csv`, saveAs: false });
  notify(`${results.length}개 방송 통계를 저장했습니다.`, { done: true });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== "START_COLLECTION") return false;
  collect(message.expectedStore).catch((error) => notify(error.message, { error: true }));
  sendResponse({ ok: true });
  return false;
});
