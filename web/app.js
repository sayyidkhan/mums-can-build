const startButton = document.querySelector("#startCall");
const callButtonLabel = document.querySelector("#callButtonLabel");
const statusBadge = document.querySelector("#status");
const talkReadiness = document.querySelector("#talkReadiness");
const voiceOrb = document.querySelector("#voiceOrb");
const transcriptLog = document.querySelector("#transcriptLog");
const eventLog = document.querySelector("#eventLog");
const remoteAudio = document.querySelector("#remoteAudio");
const healthPills = {
  fe: document.querySelector("#healthFe"),
  be: document.querySelector("#healthBe"),
  openai: document.querySelector("#healthOpenai"),
  ws: document.querySelector("#healthWs"),
  codex: document.querySelector("#healthCodex"),
};

let peerConnection;
let dataChannel;
let harnessSocket;
let localStream;
let sessionId;
let callActive = false;
const draftTranscript = new Map();
let lastSpeechStopLogAt = 0;
let currentStatus = "Idle";
let lastStatusAt = 0;
const bridgeSpeechQueue = [];
let bridgeSpeechInFlight = false;
let bridgeSpeechTimeout;
let bridgeSpeechCurrentLine = "";
let bridgeSpeechTranscriptSeen = false;

startButton.addEventListener("click", toggleCall);
window.addEventListener("online", checkConnectionHealth);
window.addEventListener("offline", () => {
  setHealth("fe", "down", "Browser is offline.");
  setHealth("be", "down", "Browser is offline.");
  setHealth("openai", "down", "Browser is offline.");
  setHealth("ws", "down", "Browser is offline.");
  setHealth("codex", "down", "Browser is offline.");
});

checkConnectionHealth();
setInterval(checkConnectionHealth, 30000);

async function checkConnectionHealth() {
  setHealth("fe", navigator.onLine ? "ok" : "down", navigator.onLine ? "Browser online." : "Browser offline.");
  setHealth("be", "checking", "Checking backend...");
  setHealth("openai", "checking", "Checking OpenAI...");
  setHealth("codex", "checking", "Checking Codex harness...");

  try {
    const response = await fetch("/health/connections", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const health = await response.json();
    setHealth("be", health.backend?.status || "down", health.backend?.reason || "Backend reachable.");
    setHealth("openai", health.openai?.status || "down", health.openai?.reason || "OpenAI status unknown.");
    setHealth("codex", health.codex?.status || "down", health.codex?.reason || "Codex harness status unknown.");
  } catch (error) {
    setHealth("be", "down", `Backend check failed: ${error.message}`);
    setHealth("openai", "down", "OpenAI check unavailable because backend is down.");
    setHealth("codex", "down", "Codex check unavailable because backend is down.");
  }

  checkWebSocketHealth();
}

function checkWebSocketHealth() {
  if (harnessSocket && harnessSocket.readyState === WebSocket.OPEN) {
    setHealth("ws", "ok", "Harness WebSocket connected.");
    return;
  }
  setHealth("ws", "checking", "Checking WebSocket...");
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const probe = new WebSocket(`${protocol}://${window.location.host}/ws/health-${crypto.randomUUID().slice(0, 8)}`);
  const timer = window.setTimeout(() => {
    setHealth("ws", "down", "WebSocket check timed out.");
    probe.close();
  }, 5000);

  probe.addEventListener("message", () => {
    window.clearTimeout(timer);
    setHealth("ws", "ok", "Harness WebSocket reachable.");
    probe.close();
  });
  probe.addEventListener("error", () => {
    window.clearTimeout(timer);
    setHealth("ws", "down", "Harness WebSocket failed.");
  });
}

function setHealth(name, status, reason) {
  const pill = healthPills[name];
  if (!pill) {
    return;
  }
  pill.classList.remove("ok", "down", "degraded", "checking");
  pill.classList.add(status);
  pill.title = reason;
}

async function toggleCall() {
  if (callActive) {
    await stopCall();
    return;
  }
  await startCall();
}

async function startCall() {
  try {
    startButton.disabled = true;
    setStatus("Connecting", false);
    sessionId = `voice-${crypto.randomUUID().slice(0, 8)}`;
    connectHarness();

    peerConnection = new RTCPeerConnection();
    dataChannel = peerConnection.createDataChannel("oai-events");
    dataChannel.addEventListener("open", () => {
      addEvent("realtime", "Data channel opened.");
      configureRealtimeSession();
      speakViaRealtime("I am ready.");
    });
    dataChannel.addEventListener("message", handleRealtimeMessage);

    peerConnection.addEventListener("track", (event) => {
      remoteAudio.srcObject = event.streams[0];
    });

    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    for (const track of localStream.getTracks()) {
      peerConnection.addTrack(track, localStream);
    }

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    const response = await fetch("/realtime/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sdp: offer.sdp }),
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const answer = await response.text();
    await peerConnection.setRemoteDescription({ type: "answer", sdp: answer });

    callActive = true;
    startButton.disabled = false;
    startButton.classList.add("ending");
    callButtonLabel.textContent = "End call";
    setStatus("Live", true);
  } catch (error) {
    addEvent("error", error.message);
    setStatus("Error", false);
    await stopCall();
  }
}

function connectHarness() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  harnessSocket = new WebSocket(`${protocol}://${window.location.host}/ws/${sessionId}`);
  harnessSocket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    setHealth("ws", "ok", "Harness WebSocket connected.");
    const message = payload.payload?.message || payload.payload?.question || payload.type;
    addEvent(payload.type, message);
    if (payload.spoken && dataChannel?.readyState === "open") {
      enqueueBridgeSpeech(payload.spoken);
    }
  });
  harnessSocket.addEventListener("open", () => addEvent("harness", `Connected session ${sessionId}.`));
  harnessSocket.addEventListener("close", () => {
    setHealth("ws", callActive ? "down" : "checking", "Harness WebSocket disconnected.");
    addEvent("harness", "Disconnected.");
  });
  harnessSocket.addEventListener("error", () => {
    setHealth("ws", "down", "Harness WebSocket error.");
  });
}

function configureRealtimeSession() {
  dataChannel.send(
    JSON.stringify({
      type: "session.update",
      session: {
        type: "realtime",
        instructions:
          "You are the voice interface for Mums Can Build. Sound natural, warm, and concise. Use short spoken phrases with natural pacing. Do not explain logs, diffs, or implementation details. If a message starts with BRIDGE:, treat it as guidance from the app and respond conversationally with the same meaning in one short sentence.",
        output_modalities: ["audio"],
        audio: {
          input: {
            transcription: {
              model: "gpt-4o-mini-transcribe",
              language: "en",
            },
            turn_detection: {
              type: "server_vad",
              silence_duration_ms: 320,
            },
          },
          output: {
            voice: "alloy",
          },
        },
      },
    }),
  );
}

function handleRealtimeMessage(event) {
  const payload = JSON.parse(event.data);
  const payloadType = payload.type;

  if (payloadType === "response.done" || payloadType === "response.audio.done") {
    markBridgeSpeechComplete();
    return;
  }

  if (payloadType === "conversation.item.input_audio_transcription.delta") {
    const transcript = payload.transcript || payload.delta || payload.text || "";
    setDraftTranscript("you", transcript);
    return;
  }

  if (payloadType === "conversation.item.input_audio_transcription.completed") {
    const transcript = payload.transcript?.trim();
    if (transcript) {
      clearDraftTranscript("you");
      addTranscript("you", transcript);
      sendTranscriptToHarness(transcript);
    }
    return;
  }

  if (payloadType === "input_audio_buffer.speech_started") {
    setStatus("Listening", true);
    return;
  }

  if (payloadType === "input_audio_buffer.speech_stopped") {
    setStatus("Thinking", true);
    const now = Date.now();
    if (now - lastSpeechStopLogAt > 1400) {
      addEvent("realtime", "Speech stopped, forwarding transcript to PM.");
      lastSpeechStopLogAt = now;
    }
    return;
  }

  if (payloadType === "response.audio_transcript.delta") {
    if (payload.transcript) {
      setDraftTranscript("assistant", payload.transcript);
    }
    return;
  }

  if (payloadType === "response.audio_transcript.done") {
    const transcript = payload.transcript?.trim();
    if (transcript) {
      clearDraftTranscript("assistant");
      addAssistantTranscriptUnique(transcript);
      bridgeSpeechTranscriptSeen = true;
    }
    markBridgeSpeechComplete();
    return;
  }
}

function sendTranscriptToHarness(text) {
  if (!harnessSocket || harnessSocket.readyState !== WebSocket.OPEN) {
    addEvent("error", "Harness socket is not ready.");
    return;
  }

  const autoStart = hasStartConfirmation(text);

  harnessSocket.send(
    JSON.stringify({
      type: "user.transcript",
      text,
      worker: "mock",
      workspace: null,
      auto_start: autoStart,
    }),
  );

  if (autoStart) {
    addEvent("pm", "Confirmation detected. Delegating to Codex.");
  }
}

function hasStartConfirmation(text) {
  const normalized = (text || "").toLowerCase().trim();
  if (!normalized) {
    return false;
  }
  return /(confirm|go ahead|proceed|start build|ship it|do it now|delegate now)/.test(normalized);
}

function speakViaRealtime(text) {
  if (!dataChannel || dataChannel.readyState !== "open") {
    return;
  }

  dataChannel.send(
    JSON.stringify({
      type: "conversation.item.create",
      item: {
        type: "message",
        role: "user",
        content: [{ type: "input_text", text: `BRIDGE: ${text}` }],
      },
    }),
  );
  dataChannel.send(
    JSON.stringify({
      type: "response.create",
      response: {
        modalities: ["audio"],
        instructions:
          "Speak naturally in one concise sentence. Preserve intent, but do not read robotically or verbatim unless explicitly asked.",
      },
    }),
  );
}

function enqueueBridgeSpeech(text) {
  if (!text || !text.trim()) {
    return;
  }
  bridgeSpeechQueue.push(text.trim());
  playNextBridgeSpeech();
}

function playNextBridgeSpeech() {
  if (bridgeSpeechInFlight || !bridgeSpeechQueue.length || !dataChannel || dataChannel.readyState !== "open") {
    return;
  }
  bridgeSpeechInFlight = true;
  const line = bridgeSpeechQueue.shift();
  bridgeSpeechCurrentLine = line;
  bridgeSpeechTranscriptSeen = false;
  speakViaRealtime(line);
  clearTimeout(bridgeSpeechTimeout);
  bridgeSpeechTimeout = window.setTimeout(markBridgeSpeechComplete, 7000);
}

function markBridgeSpeechComplete() {
  if (!bridgeSpeechInFlight) {
    return;
  }
  if (!bridgeSpeechTranscriptSeen && bridgeSpeechCurrentLine) {
    addAssistantTranscriptUnique(bridgeSpeechCurrentLine);
  }
  bridgeSpeechCurrentLine = "";
  bridgeSpeechTranscriptSeen = false;
  bridgeSpeechInFlight = false;
  clearTimeout(bridgeSpeechTimeout);
  playNextBridgeSpeech();
}

async function stopCall() {
  bridgeSpeechQueue.length = 0;
  bridgeSpeechInFlight = false;
  bridgeSpeechCurrentLine = "";
  bridgeSpeechTranscriptSeen = false;
  clearTimeout(bridgeSpeechTimeout);
  clearAllDraftTranscripts();
  for (const track of localStream?.getTracks() || []) {
    track.stop();
  }
  localStream = undefined;

  if (dataChannel && dataChannel.readyState !== "closed") {
    dataChannel.close();
  }
  dataChannel = undefined;

  if (peerConnection) {
    peerConnection.close();
  }
  peerConnection = undefined;

  if (harnessSocket && harnessSocket.readyState === WebSocket.OPEN) {
    harnessSocket.close();
  }
  harnessSocket = undefined;

  callActive = false;
  startButton.disabled = false;
  startButton.classList.remove("ending");
  callButtonLabel.textContent = "Start call";
  setStatus("Idle", false);
}

function addTranscript(speaker, text) {
  appendLine(transcriptLog, speaker, text);
}

function addAssistantTranscriptUnique(text) {
  const normalizedNext = normalizeTranscript(text);
  if (!normalizedNext) {
    return;
  }
  const lastLine = transcriptLog.lastElementChild;
  if (lastLine) {
    const metaText = lastLine.querySelector(".meta")?.textContent?.toLowerCase() || "";
    const lastText = lastLine.childNodes[1]?.textContent || "";
    if (metaText.startsWith("assistant") && normalizeTranscript(lastText) === normalizedNext) {
      return;
    }
  }
  addTranscript("assistant", text);
}

function normalizeTranscript(text) {
  return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function setDraftTranscript(speaker, text) {
  if (!text) {
    return;
  }

  const existingLine = draftTranscript.get(speaker);
  if (existingLine) {
    const meta = existingLine.querySelector(".meta");
    if (meta) {
      meta.textContent = `${speaker} (live)`;
    }
    existingLine.childNodes[1].textContent = text;
    transcriptLog.scrollTop = transcriptLog.scrollHeight;
    return;
  }

  const line = document.createElement("div");
  line.className = "line draft";
  const meta = document.createElement("span");
  meta.className = "meta";
  meta.textContent = `${speaker} (live)`;
  line.append(meta, document.createTextNode(text));
  transcriptLog.append(line);
  transcriptLog.scrollTop = transcriptLog.scrollHeight;
  draftTranscript.set(speaker, line);
}

function clearDraftTranscript(speaker) {
  const existingLine = draftTranscript.get(speaker);
  if (!existingLine) {
    return;
  }
  existingLine.remove();
  draftTranscript.delete(speaker);
}

function clearAllDraftTranscripts() {
  for (const speaker of [...draftTranscript.keys()]) {
    clearDraftTranscript(speaker);
  }
}

function addEvent(type, text) {
  appendLine(eventLog, type, text);
}

function appendLine(container, label, text) {
  const line = document.createElement("div");
  line.className = "line";
  const meta = document.createElement("span");
  meta.className = "meta";
  meta.textContent = label;
  line.append(meta, document.createTextNode(text));
  container.append(line);
  container.scrollTop = container.scrollHeight;
}

function setStatus(text, live) {
  const now = Date.now();
  if (currentStatus === "Listening" && text === "Thinking" && now - lastStatusAt < 700) {
    return;
  }
  if (currentStatus === text && now - lastStatusAt < 500) {
    return;
  }
  currentStatus = text;
  lastStatusAt = now;

  statusBadge.textContent = text;
  voiceOrb.classList.toggle("live", live);
  voiceOrb.classList.toggle("listening", text === "Listening");

  if (!talkReadiness) {
    return;
  }

  talkReadiness.classList.remove("ready", "listening", "thinking", "error");

  if (text === "Connecting") {
    talkReadiness.textContent = "Connecting mic and voice session...";
    return;
  }
  if (text === "Live") {
    talkReadiness.classList.add("ready");
    talkReadiness.textContent = 'Ready to talk. Start speaking when status changes to "Listening".';
    return;
  }
  if (text === "Listening") {
    talkReadiness.classList.add("listening");
    talkReadiness.textContent = "Listening now. Speak your request.";
    return;
  }
  if (text === "Thinking") {
    talkReadiness.classList.add("thinking");
    talkReadiness.textContent = "Got it. Processing your request...";
    return;
  }
  if (text === "Error") {
    talkReadiness.classList.add("error");
    talkReadiness.textContent = "Connection issue. Tap Start call to retry.";
    return;
  }

  talkReadiness.textContent = 'Press Start call. Speak when you see "Listening now".';
}
