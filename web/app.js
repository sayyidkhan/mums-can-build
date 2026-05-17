const startButton = document.querySelector("#startCall");
const callButtonLabel = document.querySelector("#callButtonLabel");
const statusBadge = document.querySelector("#status");
const voiceOrb = document.querySelector("#voiceOrb");
const transcriptLog = document.querySelector("#transcriptLog");
const eventLog = document.querySelector("#eventLog");
const remoteAudio = document.querySelector("#remoteAudio");

let peerConnection;
let dataChannel;
let harnessSocket;
let localStream;
let sessionId;
let callActive = false;

startButton.addEventListener("click", toggleCall);

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
    const message = payload.payload?.message || payload.payload?.question || payload.type;
    addEvent(payload.type, message);
    if (payload.spoken && dataChannel?.readyState === "open") {
      speakViaRealtime(payload.spoken);
    }
  });
  harnessSocket.addEventListener("open", () => addEvent("harness", `Connected session ${sessionId}.`));
  harnessSocket.addEventListener("close", () => addEvent("harness", "Disconnected."));
}

function configureRealtimeSession() {
  dataChannel.send(
    JSON.stringify({
      type: "session.update",
      session: {
        type: "realtime",
        instructions:
          "You are the voice interface for Mums Can Build. Keep speech very short. Do not explain logs, diffs, or implementation details. When the app sends a message beginning with SAY:, say exactly the text after SAY: and nothing else.",
        output_modalities: ["audio"],
        audio: {
          input: {
            transcription: {
              model: "gpt-4o-mini-transcribe",
              language: "en",
            },
            turn_detection: {
              type: "server_vad",
              silence_duration_ms: 700,
            },
          },
          output: {
            voice: "marin",
          },
        },
      },
    }),
  );
}

function handleRealtimeMessage(event) {
  const payload = JSON.parse(event.data);

  if (payload.type === "conversation.item.input_audio_transcription.completed") {
    const transcript = payload.transcript?.trim();
    if (transcript) {
      addTranscript("you", transcript);
      sendTranscriptToHarness(transcript);
    }
    return;
  }

  if (payload.type === "response.audio_transcript.done" && payload.transcript) {
    addTranscript("assistant", payload.transcript);
    return;
  }

  if (payload.type === "input_audio_buffer.speech_started") {
    setStatus("Listening", true);
    return;
  }

  if (payload.type === "input_audio_buffer.speech_stopped") {
    setStatus("Thinking", true);
  }
}

function sendTranscriptToHarness(text) {
  if (!harnessSocket || harnessSocket.readyState !== WebSocket.OPEN) {
    addEvent("error", "Harness socket is not ready.");
    return;
  }

  harnessSocket.send(
    JSON.stringify({
      type: "user.transcript",
      text,
      worker: "mock",
      workspace: null,
    }),
  );
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
        content: [{ type: "input_text", text: `SAY: ${text}` }],
      },
    }),
  );
  dataChannel.send(
    JSON.stringify({
      type: "response.create",
      response: {
        modalities: ["audio"],
        instructions: `Say exactly this and nothing else: ${JSON.stringify(text)}`,
      },
    }),
  );
}

async function stopCall() {
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
  statusBadge.textContent = text;
  voiceOrb.classList.toggle("live", live);
}
