const collectButton = document.getElementById("collect");
const storeSelect = document.getElementById("store");
const status = document.getElementById("status");

collectButton.addEventListener("click", async () => {
  collectButton.disabled = true;
  status.textContent = "목록을 확인하는 중입니다…";
  try {
    const response = await chrome.runtime.sendMessage({
      type: "START_COLLECTION",
      expectedStore: storeSelect.value
    });
    if (!response?.ok) throw new Error(response?.error || "수집을 시작하지 못했습니다.");
    status.textContent = "수집을 시작했습니다. 완료되면 CSV가 다운로드됩니다.";
  } catch (error) {
    status.textContent = error.message;
    collectButton.disabled = false;
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== "COLLECTION_PROGRESS") return;
  status.textContent = message.text;
  if (message.done || message.error) collectButton.disabled = false;
});
