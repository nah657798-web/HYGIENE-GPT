const API_BASE = window.HYGIENEGPT_API_URL || "http://127.0.0.1:8000";

const form = document.querySelector("#chat-form");
const input = document.querySelector("#question-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const sourcesList = document.querySelector("#sources-list");
const sourceCount = document.querySelector("#source-count");
const connectionStatus = document.querySelector("#connection-status");
const micButton = document.querySelector("#mic-button");
const voiceLanguage = document.querySelector("#voice-language");

function setConnectionStatus(message, state = "") {
  connectionStatus.textContent = message;
  connectionStatus.className = `connection-status ${state}`.trim();
}

async function checkServer() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    if (!response.ok) throw new Error("API unavailable");
    const health = await response.json();
    setConnectionStatus(
      health.indexed_passages > 0
        ? `Connected · ${health.indexed_passages} source passages indexed`
        : "Connected · add trusted PDFs and build the knowledge base to start answering",
      "online",
    );
  } catch {
    setConnectionStatus("Server not connected. Start the API using the instructions in the README.", "offline");
  }
}

function appendMessage(role, text, citations = []) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;

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
    appendAnswerWithCitations(paragraph, text, citations);
  }
  content.append(paragraph);

  if (role !== "user" && text && citations.length) {
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
      button.textContent = `[${citation.citation_id}]`;
      button.setAttribute("aria-label", `Show source ${citation.citation_id}`);
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
    empty.innerHTML = '<div class="empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 3.75h8l4 4v12.5H6z"></path><path d="M14 3.75v4h4M9 12h6m-6 3.5h6"></path></svg></div><h3>No supporting sources returned</h3><p>Try a question covered by the documents added to this project.</p>';
    sourcesList.append(empty);
    return;
  }

  for (const citation of citations) {
    const card = document.createElement("article");
    card.className = "source-card";
    card.id = `source-${citation.citation_id}`;

    const top = document.createElement("div");
    top.className = "source-card-top";
    const titleGroup = document.createElement("div");
    const title = document.createElement("h3");
    title.className = "source-title";
    title.textContent = citation.source || "Source document";
    const meta = document.createElement("p");
    meta.className = "source-meta";
    const details = [citation.organization, citation.year, `PDF page ${citation.page}`].filter(Boolean);
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
        // Ignore malformed source URLs while keeping the citation and passage visible.
      }
    }
    sourcesList.append(card);
  }
}

function highlightCitation(citationId, citations) {
  document.querySelectorAll(".source-card.highlighted").forEach((card) => card.classList.remove("highlighted"));
  let target = document.querySelector(`#source-${CSS.escape(citationId)}`);
  if (!target) {
    renderSources(citations);
    target = document.querySelector(`#source-${CSS.escape(citationId)}`);
  }
  if (!target) return;
  target.classList.add("highlighted");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
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

async function askQuestion(question) {
  appendMessage("user", question);
  sendButton.disabled = true;
  input.disabled = true;
  const loading = document.createElement("div");
  loading.className = "message assistant-message";
  loading.id = "loading-message";
  loading.innerHTML = '<div class="avatar" aria-hidden="true">H</div><div class="message-content"><div class="message-label">HygieneGPT <span class="label-dot"></span></div><p class="typing-indicator">Checking the trusted documents…</p></div>';
  conversation.append(loading);
  conversation.scrollTop = conversation.scrollHeight;

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The server could not answer right now.");
    appendMessage("assistant", data.answer, data.citations || []);
    renderSources(data.citations || []);
  } catch (error) {
    appendMessage("assistant", error.message || "I could not reach the server. Please try again.");
    renderSources([]);
  } finally {
    loading.remove();
    sendButton.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

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
  input.style.height = `${Math.min(input.scrollHeight, 105)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.textContent;
    input.focus();
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 105)}px`;
  });
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

checkServer();
setInterval(checkServer, 30000);
