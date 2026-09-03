const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitFor(predicate, timeoutMilliseconds = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMilliseconds) {
    const value = predicate();
    if (value) return value;
    await sleep(250);
  }
  throw new Error("네이버 화면의 통계 데이터 로딩 시간이 초과되었습니다.");
}

function collectList() {
  if (!location.pathname.includes("/l/v1/broadcasts")) {
    throw new Error("쇼핑라이브 관리툴의 라이브 목록에서 실행해주세요.");
  }
  const rows = Array.from(document.querySelectorAll("tr"));
  const broadcasts = [];
  for (const row of rows) {
    const text = row.innerText.replace(/\s+/g, " ").trim();
    if (!/(^|\s)종료(\s|$)/.test(text)) continue;
    const statsLink = Array.from(row.querySelectorAll("a")).find((link) => /\/broadcasts\/\d+\/stats/.test(link.href));
    const idMatch = statsLink?.href.match(/\/broadcasts\/(\d+)\/stats/);
    const dateMatch = text.match(/(20\d{2})\.(\d{2})\.(\d{2})\s+(\d{2}:\d{2})/);
    if (!statsLink || !idMatch || !dateMatch) continue;
    const date = `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
    broadcasts.push({
      broadcastId: idMatch[1],
      broadcastAt: `${date} ${dateMatch[4]}`,
      title: text.replace(/^\d+\s+종료\s+\d+\s+/, "").split(dateMatch[0])[0].trim(),
      statsUrl: statsLink.href
    });
  }
  if (!broadcasts.length) {
    throw new Error("현재 조회 결과에서 종료된 방송의 통계 링크를 찾지 못했습니다.");
  }
  return broadcasts;
}

function visibleElements() {
  return Array.from(document.querySelectorAll("button,[role='button'],[role='option'],li,div,span"))
    .filter((element) => element.getClientRects().length > 0);
}

async function selectLiveDuring() {
  const bodyText = document.body.innerText;
  if (!bodyText.includes("라이브 상태별 데이터")) {
    throw new Error("라이브 통계 화면을 찾지 못했습니다.");
  }
  const trigger = visibleElements().find((element) => {
    const text = element.innerText?.replace(/\s+/g, " ").trim();
    return text === "라이브 상태를 선택하세요" || text === "전체 라이브 대기 ~ 현재";
  });
  if (!trigger) throw new Error("라이브 상태 선택 메뉴를 찾지 못했습니다.");
  trigger.click();
  const liveOption = await waitFor(() => visibleElements().find((element) => {
    const text = element.innerText?.replace(/\s+/g, " ").trim();
    return text === "라이브중 라이브 시작 ~ 종료";
  }));
  liveOption.click();
  await sleep(700);
}

function numberFrom(text, expression, label) {
  const match = text.match(expression);
  if (!match) throw new Error(`${label} 값을 찾지 못했습니다.`);
  return Number(match[1].replace(/,/g, ""));
}

async function extractStats(expectedStore, item) {
  await waitFor(() => document.body.innerText.includes("라이브 통계"));
  const initialText = document.body.innerText;
  if (!initialText.includes(expectedStore)) {
    throw new Error(`현재 통계 계정이 '${expectedStore}'이(가) 아닙니다.`);
  }
  await selectLiveDuring();
  const text = await waitFor(() => {
    const current = document.body.innerText;
    return /시청수\s*[\r\n ]+[\d,]+\s*뷰/.test(current) ? current : null;
  });
  const viewers = numberFrom(text, /시청수\s*[\r\n ]+([\d,]+)\s*뷰/, "라이브중 시청수");
  const paidMatch = text.match(/결제 상품수\s*[\r\n ]+([\d,]+)\s*개\s*\(([\d,]+)\s*명\)/);
  if (!paidMatch) throw new Error("결제 상품수와 유니크 결제자수를 찾지 못했습니다.");
  const updatedMatch = text.match(/(20\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s*에 데이터 업데이트/);
  return {
    "계정": expectedStore,
    "방송 ID": item.broadcastId,
    "방송 제목": item.title,
    "방송일시": item.broadcastAt,
    "라이브중 시청수": viewers,
    "유니크 결제자수": Number(paidMatch[2].replace(/,/g, "")),
    "결제 상품수": Number(paidMatch[1].replace(/,/g, "")),
    "데이터 업데이트 시각": updatedMatch ? updatedMatch[1].replaceAll(".", "-") : ""
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  (async () => {
    if (message.type === "COLLECT_LIST") return collectList();
    if (message.type === "EXTRACT_STATS") return extractStats(message.expectedStore, message.item);
    return null;
  })().then((data) => sendResponse({ ok: true, data })).catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});
