let callObject = null;
let ws = null;
let connected = false;
let startTime = null;
let durationInterval = null;
let micEnabled = true;

const MERGE_WINDOW_MS = 3000;
let lastRow = null;
let mergeTimer = null;

const preConnect = document.getElementById("pre-connect");
const callEl = document.getElementById("call");
const startBtn = document.getElementById("start-btn");
const agentOrb = document.getElementById("agent-orb");
const captionSpeaker = document.getElementById("caption-speaker");
const captionText = document.getElementById("caption-text");
const transcriptPanel = document.getElementById("transcript-panel");
const micBtn = document.getElementById("mic-btn");
const endBtn = document.getElementById("end-btn");
const durationEl = document.getElementById("duration");
const remoteAudio = document.getElementById("remote-audio");

async function connect() {
  startBtn.disabled = true;
  startBtn.textContent = "Connecting...";

  try {
    const res = await fetch("/api/create-room", { method: "POST" });
    const { room_url, token, error } = await res.json();
    if (error) throw new Error(error);

    callObject = DailyIframe.createCallObject({
      audioSource: true,
      videoSource: false,
    });

    callObject.on("joined-meeting", () => {
      console.log("Joined Daily room");
    });

    callObject.on("error", (e) => {
      console.error("Daily error:", e);
    });

    callObject.on("left-meeting", () => {
      console.log("Left Daily room");
    });

    callObject.on("track-started", (event) => {
      if (event.track.kind === "audio" && event.participant && !event.participant.local) {
        remoteAudio.srcObject = new MediaStream([event.track]);
      }
    });

    await callObject.join({ url: room_url, token });

    const wsProtocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${wsProtocol}//${location.host}/ws/transcripts`);
    ws.onmessage = handleMessage;
    ws.onclose = () => console.log("WebSocket closed");

    connected = true;
    preConnect.classList.add("hidden");
    callEl.classList.remove("hidden");
    startTimer();
    agentOrb.className = "orb orb--large orb--listening";
  } catch (err) {
    console.error("Connection failed:", err);
    startBtn.disabled = false;
    startBtn.textContent = "Start Call";
    cleanup();
  }
}

function handleMessage(event) {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case "transcript":
      removePartialRow();
      addTranscriptRow(msg.data);
      updateCaption(msg.data.speaker, msg.data.text);
      if (msg.data.speaker === "user") {
        agentOrb.className = "orb orb--large orb--thinking";
      } else {
        agentOrb.className = "orb orb--large orb--speaking";
      }
      break;
    case "partial":
      updateCaption("user", msg.data.text);
      updatePartialRow(msg.data.text);
      agentOrb.className = "orb orb--large orb--listening";
      break;
    case "agent_speaking":
      agentOrb.className = "orb orb--large orb--speaking";
      break;
    case "agent_idle":
      agentOrb.className = "orb orb--large orb--listening";
      break;
  }
}

function addTranscriptRow(data) {
  const now = Date.now();
  const isAgent = data.speaker === "agent";

  if (
    lastRow &&
    lastRow.speaker === data.speaker &&
    now - lastRow.ts < MERGE_WINDOW_MS
  ) {
    const textEl = lastRow.el.querySelector(".transcript-row__text");
    textEl.textContent += " " + data.text;
    lastRow.ts = now;

    clearTimeout(mergeTimer);
    mergeTimer = setTimeout(() => { lastRow = null; }, MERGE_WINDOW_MS);

    transcriptPanel.scrollTop = transcriptPanel.scrollHeight;
    return;
  }

  const row = document.createElement("div");
  row.className = "transcript-row";
  row.innerHTML = `
    <span class="transcript-row__time">${data.timestamp}</span>
    <span class="transcript-row__speaker ${
      isAgent ? "transcript-row__speaker--agent" : "transcript-row__speaker--user"
    }">
      ${isAgent ? "Agent" : "You"}
    </span>
    <span class="transcript-row__text">${escapeHtml(data.text)}</span>
  `;
  transcriptPanel.appendChild(row);
  transcriptPanel.scrollTop = transcriptPanel.scrollHeight;

  clearTimeout(mergeTimer);
  lastRow = { el: row, speaker: data.speaker, ts: now };
  mergeTimer = setTimeout(() => { lastRow = null; }, MERGE_WINDOW_MS);
}

function updateCaption(speaker, text) {
  captionSpeaker.textContent = speaker === "agent" ? "Agent:" : "You:";
  captionText.textContent = text;
}

function updatePartialRow(text) {
  let row = document.getElementById("partial-row");
  if (!row) {
    row = document.createElement("div");
    row.id = "partial-row";
    row.className = "transcript-row transcript-row--partial";
    transcriptPanel.appendChild(row);
  }
  row.innerHTML = `
    <span class="transcript-row__time"></span>
    <span class="transcript-row__speaker transcript-row__speaker--user">You</span>
    <span class="transcript-row__text">${escapeHtml(text)}</span>
  `;
  transcriptPanel.scrollTop = transcriptPanel.scrollHeight;
}

function removePartialRow() {
  const row = document.getElementById("partial-row");
  if (row) row.remove();
}

function toggleMic() {
  if (!callObject) return;
  micEnabled = !micEnabled;
  callObject.setLocalAudio(micEnabled);
  micBtn.className = `control-btn ${
    micEnabled ? "control-btn--default" : "control-btn--muted"
  }`;
}

function endCall() {
  endBtn.disabled = true;
  endBtn.textContent = "Ending...";
  stopTimer();

  if (callObject) {
    callObject.leave();
    callObject.destroy();
    callObject = null;
  }

  connected = false;
  resetToStart();
}

function resetToStart() {
  cleanup();
  preConnect.classList.remove("hidden");
  callEl.classList.add("hidden");
  startBtn.disabled = false;
  startBtn.textContent = "Start Call";
  transcriptPanel.innerHTML = "";
  captionText.textContent = "Waiting for speech...";
  captionSpeaker.textContent = "";
  durationEl.textContent = "";
  endBtn.disabled = false;
  endBtn.textContent = "End Call";
  lastRow = null;
  clearTimeout(mergeTimer);
}

function startTimer() {
  startTime = Date.now();
  durationInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const mins = String(Math.floor(elapsed / 60)).padStart(2, "0");
    const secs = String(elapsed % 60).padStart(2, "0");
    durationEl.textContent = `${mins}:${secs}`;
  }, 1000);
}

function stopTimer() {
  if (durationInterval) {
    clearInterval(durationInterval);
    durationInterval = null;
  }
}

function cleanup() {
  if (callObject) {
    callObject.leave();
    callObject.destroy();
    callObject = null;
  }
  if (ws) {
    ws.close();
    ws = null;
  }
  connected = false;
  stopTimer();
}

function escapeHtml(text) {
  const el = document.createElement("div");
  el.textContent = text;
  return el.innerHTML;
}
