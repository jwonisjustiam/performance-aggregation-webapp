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
  const statsLinks = Array.from(document.querySelectorAll("a[href]"))
    .filter((link) => {
      const label = link.innerText?.replace(/\s+/g, " ").trim();
      return label === "통계" || /\/broadcasts\/\d+\/stats(?:\?|$)/.test(link.href);
    });
  const broadcasts = [];
  const seenIds = new Set();
  for (const statsLink of statsLinks) {
    const idMatch = statsLink?.href.match(/\/broadcasts\/(\d+)\/stats/);
    if (!idMatch || seenIds.has(idMatch[1])) continue;
    let container = statsLink;
    let text = "";
    let dateMatch = null;
    for (let depth = 0; container && depth < 12; depth += 1, container = container.parentElement) {
      text = container.innerText?.replace(/\s+/g, " ").trim() || "";
      dateMatch = text.match(/(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})(?:일|\.)?\s*(?:(오전|오후)\s*)?(\d{1,2}):(\d{2})/);
      if (dateMatch) break;
    }
    if (!dateMatch) continue;
    let hour = Number(dateMatch[5]);
    if (dateMatch[4] === "오후" && hour < 12) hour += 12;
    if (dateMatch[4] === "오전" && hour === 12) hour = 0;
    const date = `${dateMatch[1]}-${dateMatch[2].padStart(2, "0")}-${dateMatch[3].padStart(2, "0")}`;
    const time = `${String(hour).padStart(2, "0")}:${dateMatch[6]}`;
    const titleElement = container?.querySelector("h1,h2,h3,h4,[class*='title'],img[alt]");
    const title = titleElement?.innerText?.trim() || titleElement?.getAttribute?.("alt") || `방송 ${idMatch[1]}`;
    seenIds.add(idMatch[1]);
    broadcasts.push({
      broadcastId: idMatch[1],
      broadcastAt: `${date} ${time}`,
      title,
      statsUrl: statsLink.href
    });
  }
  if (!broadcasts.length) {
    throw new Error(
      `현재 조회 결과에서 통계 링크를 찾지 못했습니다. 날짜 조회 후 종료 방송의 '통계' 버튼이 보이는지 확인해주세요. ` +
      `(화면의 통계 링크 ${statsLinks.length}개)`
    );
  }
  return broadcasts;
}

function visibleElements() {
  return Array.from(document.querySelectorAll("button,[role='button'],[role='option'],li,div,span,strong,h1,h2,h3,h4,h5"))
    .filter((element) => element.getClientRects().length > 0);
}

async function selectLiveDuring() {
  const trigger = await waitFor(() => {
    const labelled = document.querySelector('[aria-label="라이브 상태를 선택하세요"]');
    if (labelled?.getClientRects().length) return labelled;
    return visibleElements().find((element) => {
      const text = element.innerText?.replace(/\s+/g, " ").trim();
      return text === "전체 라이브 대기 ~ 현재" || text === "라이브 상태를 선택하세요";
    });
  });
  trigger.click();
  const liveOption = await waitFor(() => visibleElements().find((element) => {
    const text = element.innerText?.replace(/\s+/g, " ").trim();
    return element.getAttribute?.("role") === "option" && text?.startsWith("라이브중");
  }));
  liveOption.click();
  await waitFor(() => {
    const current = document.querySelector('[aria-label="라이브 상태를 선택하세요"]');
    return current?.innerText?.replace(/\s+/g, " ").trim().startsWith("라이브중");
  });
}

function numberFrom(text, expression, label) {
  const match = text.match(expression);
  if (!match) throw new Error(`${label} 값을 찾지 못했습니다.`);
  return Number(match[1].replace(/,/g, ""));
}

function statBlockText(title, valueExpression) {
  const titleElement = visibleElements().find((element) => {
    const text = element.innerText?.replace(/\s+/g, " ").trim();
    return text === title;
  });
  let container = titleElement?.parentElement;
  for (let depth = 0; container && depth < 8; depth += 1, container = container.parentElement) {
    const text = container.innerText?.replace(/\s+/g, " ").trim() || "";
    if (valueExpression.test(text)) return text;
  }
  return null;
}

async function extractStats(expectedStore, item) {
  await selectLiveDuring();
  const viewerText = await waitFor(() => statBlockText(
    "시청/알림 통계",
    /(?:^|\s)시청수(?!\s*\()\s+[\d,]+\s*뷰/
  ));
  const viewers = numberFrom(
    viewerText,
    /(?:^|\s)시청수(?!\s*\()\s+([\d,]+)\s*뷰/,
    "시청/알림 통계의 시청수"
  );
  const paymentText = await waitFor(() => statBlockText(
    "결제 통계",
    /결제 상품수\s+[\d,]+\s*개\s*\([\d,]+\s*명\)/
  ));
  const paidMatch = paymentText.match(/결제 상품수\s+([\d,]+)\s*개\s*\(([\d,]+)\s*명\)/);
  if (!paidMatch) throw new Error("결제 상품수와 유니크 결제자수를 찾지 못했습니다.");
  const updatedMatch = document.body.innerText.match(/(20\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s*에 데이터 업데이트/);
  return {
    "계정": expectedStore,
    "방송 ID": item.broadcastId,
    "방송 제목": item.title,
    "방송일시": item.broadcastAt,
    "시청수": viewers,
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
