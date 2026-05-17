# Resources

## OpenAI Realtime

- https://developers.openai.com/api/docs/models/gpt-realtime-2
- https://developers.openai.com/api/docs/guides/realtime
- https://developers.openai.com/api/docs/guides/realtime-websocket

## Notes

- Use `gpt-realtime-2` for the voice PM.
- For browser/mobile audio, prefer WebRTC later.
- For the first backend harness POC, WebSocket is acceptable because the server owns the harness and can stream events.
- The browser call POC uses WebRTC for audio and a separate harness WebSocket for builder events.
- Keep voice responses short. The user is listening, not reading.
- The voice PM should give high-level progress only:
  - "I am checking what you need."
  - "I have enough. I am preparing the build task."
  - "I am starting the builder now."
  - "The builder is editing files."
  - "The first version is ready."
- Detailed logs should be stored or streamed as text events, but not spoken unless the user asks.

## Local Contracts

- See `docs/CONTRACTS.md` for the current WebSocket event contract, Codex task shape, and spoken update policy implemented by the POC.
