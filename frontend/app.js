const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE = window.HYGIENEGPT_API_URL || (isLocalHost ? "http://127.0.0.1:8000" : "");

const shell = document.querySelector("#app-shell");
const workspace = document.querySelector("#workspace");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#question-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
const historyList = document.querySelector("#history-list");
const historyEmpty = document.querySelector("#history-empty");
const activeChatTitle = document.querySelector("#active-chat-title");
const sourcesList = document.querySelector("#sources-list");
const sourceCount = document.querySelector("#source-count");
const connectionStatus = document.querySelector("#connection-status");
const micButton = document.querySelector("#mic-button");
const voiceLanguage = document.querySelector("#voice-language");

let chats = [];
let activeChatId = null;
let loadingNode = null;

function setConnectionStatus(message, state) {
  connectionStatus.textContent = message;
  connectionStatus.className = "connection-status" + (state ? " " + state : "");
}

function newChat() {
  const chat = {
    id: String(Date.now()) + "-" + Math.random().toString(36).slice(2, 8),
    title: "New hygiene chat",
    messages: [],
  };
  chats.unshift(chat);
  activeChatId = chat.id;
  renderHistory();
  renderActiveChat();
  renderSources([]);
  closeSidebarOnMobile();
}

function getActiveChat() {
  return chats.find((chat) => chat.id === activeChatId);
}

function renderHistory() {
  historyList.replaceChildren();
  historyEmpty.hidden = chats.length > 0;

  for (const chat of chats) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item" + (chat.id === activeChatId ? " active" : "");
    const icon = document.createElement("span");
    icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H20v16H7.5A2.5 2.5 0 0 1 5 16.5v-11Z"></path><path d="M5 16.5A2.5 2.5 0 0 1 7.5 14H20"></path></svg>';
    const label = document.createElement("span");
    label.textContent = chat.title;
    button.append(icon, label);
    button.addEventListener("click", () => {
      activeChatId = chat.id;
      renderHistory();
      renderActiveChat();
      const lastAnswer = [...chat.messages].reverse().find((message) => message.role === "assistant");
      renderSources(lastAnswer ? lastAnswer.citations || [] : []);
      closeSidebarOnMobile();
    });
    historyList.append(button);
  }
}

function renderActiveChat() {
  const chat = getActiveChat();
  if (!chat) return;
  activeChatTitle.textContent = chat.title;
  welcome.hidden = chat.messages.length > 0;
  conversation.replaceChildren();
  for (const message of chat.messages) {
    appendMessage(message.role, message.text, message.citations || []);
  }
}

function appendMessage(role, text, citations) {
  const wrapper = document.createElement("div");
  wrapper.className = "message " + (role === "user" ? "user-message" : "assistant-message");

  if (role !== "user") {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "H";
    wrapper.append(avatar);
  }

  const content = document.createElement("div");
  content.className = "message-content";

  if (role !== "user") {
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = "HygieneGPT";
    const dot = document.createElement("span");
    dot.className = "label-dot";
    label.append(dot);
    content.append(label);
  }

  const paragraph = document.createElement("p");
  if (role === "user") {
    paragraph.textContent = text;
  } else {
    paragraph.className = "assistant-answer";
    appendAnswerWithCitations(paragraph, text, citations || []);
  }
  content.append(paragraph);

  if (role !== "user" && text && citations && citations.length) {
    const tools = document.createElement("div");
    tools.className = "message-tools";
    const speak = document.createElement("button");
    speak.type = "button";
    speak.className = "speak-answer";
    speak.setAttribute("aria-label", "Read answer aloud");
    speak.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5Z"></path><path d="M15 9a5 5 0 0 1 0 6m3-9a9 9 0 0 1 0 12"></path></svg><span>Listen</span>';
    speak.addEventListener("click", () => speakText(text));
    tools.append(speak);
    content.append(tools);
  }

  wrapper.append(content);
  conversation.append(wrapper);
  conversation.scrollTop = conversation.scrollHeight;
}

function appendAnswerWithCitations(element, text, citations) {
  const byId = new Map(citations.map((citation) => [citation.citation_id, citation]));
  const citationPattern = /\[(S\d+)\]/g;
  let cursor = 0;
  let match;

  while ((match = citationPattern.exec(text)) !== null) {
    element.append(document.createTextNode(text.slice(cursor, match.index)));
    const citation = byId.get(match[1]);
    if (citation) {
      const button = document.createElement("button");
      button.className = "citation-inline";
      button.type = "button";
      button.textContent = "[" + citation.citation_id + "]";
      button.setAttribute("aria-label", "Show source " + citation.citation_id);
      button.addEventListener("click", () => highlightCitation(citation.citation_id, citations));
      element.append(button);
    } else {
      element.append(document.createTextNode(match[0]));
    }
    cursor = citationPattern.lastIndex;
  }
  element.append(document.createTextNode(text.slice(cursor)));
}

function renderSources(citations) {
  sourceCount.textContent = String(citations.length);
  sourcesList.replaceChildren();

  if (!citations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-sources";
    empty.innerHTML = '<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 3.75h8l4 4v12.5H6z"></path><path d="M14 3.75v4h4M9 12h6m-6 3.5h6"></path></svg></div><h3>No sources yet</h3><p>Ask a question to see the trusted document passage and PDF page.</p>';
    sourcesList.append(empty);
    return;
  }

  for (const citation of citations) {
    const card = document.createElement("article");
    card.className = "source-card";
    card.id = "source-" + citation.citation_id;

    const top = document.createElement("div");
    top.className = "source-card-top";
    const titleGroup = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "source-title";
    title.textContent = citation.source || "Source document";
    const meta = document.createElement("p");
    meta.className = "source-meta";
    const details = [citation.organization, citation.year, "PDF page " + citation.page].filter(Boolean);
    meta.textContent = details.join(" · ");
    titleGroup.append(title, meta);

    const badge = document.createElement("span");
    badge.className = "source-id";
    badge.textContent = citation.citation_id;
    top.append(titleGroup, badge);

    const excerpt = document.createElement("p");
    excerpt.className = "source-excerpt";
    excerpt.textContent = citation.text;
    card.append(top, excerpt);

    if (citation.url) {
      try {
        const linkUrl = new URL(citation.url);
        if (linkUrl.protocol === "https:" || linkUrl.protocol === "http:") {
          const link = document.createElement("a");
          link.className = "source-link";
          link.href = linkUrl.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open original document ↗";
          card.append(link);
        }
      } catch {
        // Keep the passage visible when a source URL is malformed.
      }
    }
    sourcesList.append(card);
  }
}

function highlightCitation(citationId, citations) {
  document.querySelectorAll(".source-card.highlighted").forEach((card) => card.classList.remove("highlighted"));
  let target = document.querySelector("#source-" + CSS.escape(citationId));
  if (!target) {
    renderSources(citations);
    target = document.querySelector("#source-" + CSS.escape(citationId));
  }
  if (!target) return;
  target.classList.add("highlighted");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  if (window.innerWidth <= 820) workspace.classList.add("sources-open");
}

function saveMessage(role, text, citations) {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.push({ role, text, citations: citations || [] });
  if (role === "user" && chat.title === "New hygiene chat") {
    chat.title = text.trim().slice(0, 38) + (text.trim().length > 38 ? "…" : "");
    activeChatTitle.textContent = chat.title;
    renderHistory();
  }
}

function removeLoading() {
  if (loadingNode) {
    loadingNode.remove();
    loadingNode = null;
  }
}

async function askQuestion(question) {
  const chat = getActiveChat();
  if (!chat || !question.trim() || sendButton.disabled) return;

  welcome.hidden = true;
  saveMessage("user", question, []);
  appendMessage("user", question, []);
  sendButton.disabled = true;
  input.disabled = true;

  loadingNode = document.createElement("div");
  loadingNode.className = "message assistant-message";
  loadingNode.innerHTML = '<div class="avatar" aria-hidden="true">H</div><div class="message-content"><div class="message-label">HygieneGPT <span class="label-dot"></span></div><p class="typing-indicator">Checking the trusted documents</p></div>';
  conversation.append(loadingNode);
  conversation.scrollTop = conversation.scrollHeight;

  try {
    const response = await fetch(API_BASE + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The server could not answer right now.");

    removeLoading();
    saveMessage("assistant", data.answer, data.citations || []);
    appendMessage("assistant", data.answer, data.citations || []);
    renderSources(data.citations || []);
  } catch (error) {
    removeLoading();
    const message = error.message || "I could not reach the server. Please try again.";
    saveMessage("assistant", message, []);
    appendMessage("assistant", message, []);
    renderSources([]);
  } finally {
    removeLoading();
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

function closeSidebarOnMobile() {
  if (window.innerWidth <= 820) shell.classList.remove("sidebar-open");
}

function speakText(text) {
  if (!("speechSynthesis" in window)) {
    setConnectionStatus("Speech playback is not available in this browser.", "offline");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = voiceLanguage.value;
  window.speechSynthesis.speak(utterance);
}

document.querySelector("#new-chat-button").addEventListener("click", newChat);
document.querySelector("#sidebar-toggle").addEventListener("click", () => shell.classList.toggle("sidebar-open"));
document.querySelector("#sources-toggle").addEventListener("click", () => {
  if (window.innerWidth <= 820) {
    workspace.classList.toggle("sources-open");
  } else {
    workspace.classList.toggle("sources-collapsed");
  }
});
document.querySelector("#sources-close").addEventListener("click", () => {
  if (window.innerWidth <= 820) workspace.classList.remove("sources-open");
  else workspace.classList.add("sources-collapsed");
});
document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => askQuestion(button.querySelector("small").textContent));
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question || sendButton.disabled) return;
  input.value = "";
  input.style.height = "auto";
  askQuestion(question);
});
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 132) + "px";
});
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    newChat();
    input.focus();
  }
  if (event.key === "Escape") {
    shell.classList.remove("sidebar-open");
    workspace.classList.remove("sources-open");
  }
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  const recognition = new SpeechRecognition();
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  micButton.addEventListener("click", () => {
    recognition.lang = voiceLanguage.value;
    try {
      recognition.start();
    } catch {
      recognition.stop();
    }
  });
  recognition.addEventListener("start", () => {
    micButton.classList.add("listening");
    micButton.setAttribute("aria-label", "Listening");
  });
  recognition.addEventListener("end", () => {
    micButton.classList.remove("listening");
    micButton.setAttribute("aria-label", "Speak your question");
  });
  recognition.addEventListener("result", (event) => {
    input.value = event.results[0][0].transcript;
    input.dispatchEvent(new Event("input"));
    input.focus();
  });
  recognition.addEventListener("error", () => setConnectionStatus("Voice input was unavailable. You can type your question instead.", "offline"));
} else {
  micButton.disabled = true;
  micButton.title = "Voice input is not supported in this browser";
  micButton.setAttribute("aria-label", "Voice input is not supported in this browser");
}

newChat();

async function checkServer() {
  try {
    const response = await fetch(API_BASE + "/api/health");
    if (!response.ok) throw new Error("API unavailable");
    const health = await response.json();
    setConnectionStatus(
      health.indexed_passages > 0
        ? health.indexed_passages + " source passages ready"
        : "No readable trusted PDF passages were found",
      health.indexed_passages > 0 ? "online" : "offline",
    );
  } catch {
    setConnectionStatus("Unable to connect to the server. Try again in a moment.", "offline");
  }
}
checkServer();
setInterval(checkServer, 30000);
