import { useEffect, useRef } from "react";

/**
 * Subscribe to backend WebSocket and invoke onUpdate(payload) on every message.
 * Payload shape: { type: "fixture_update", event_id, fixture }
 *
 * Optional `pollFallback`: if provided as a function returning a promise, the hook
 * will poll it every `POLL_FALLBACK_MS` whenever the WebSocket has been disconnected
 * for more than the threshold. This ensures realtime continues even on flaky networks
 * or when ingress upgrades fail.
 */
const PING_INTERVAL_MS = 25000;
const MAX_RECONNECT_DELAY_MS = 30000;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RETRY_EXPONENT = 6;
const POLL_FALLBACK_MS = 6000;

export default function useFixtureSocket(onUpdate, pollFallback) {
  const onUpdateRef = useRef(onUpdate);
  const pollRef = useRef(pollFallback);
  useEffect(() => { onUpdateRef.current = onUpdate; }, [onUpdate]);
  useEffect(() => { pollRef.current = pollFallback; }, [pollFallback]);

  useEffect(() => {
    const backend = process.env.REACT_APP_BACKEND_URL || "";
    const wsUrl = backend.replace(/^http/, "ws") + "/api/ws";
    let ws;
    let pingTimer;
    let pollTimer;
    let socketHealthy = false;
    let stopped = false;
    let retry = 0;

    const startPolling = () => {
      if (pollTimer || !pollRef.current) return;
      pollTimer = setInterval(() => {
        if (socketHealthy || stopped) return;
        Promise.resolve(pollRef.current()).catch((err) =>
          console.error("[useFixtureSocket] poll fallback failed:", err)
        );
      }, POLL_FALLBACK_MS);
    };

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    const connect = () => {
      if (stopped) return;
      try {
        ws = new WebSocket(wsUrl);
      } catch (err) {
        console.error("[useFixtureSocket] WebSocket constructor failed:", err);
        startPolling();
        scheduleReconnect();
        return;
      }
      ws.onopen = () => {
        retry = 0;
        socketHealthy = true;
        stopPolling();
        pingTimer = setInterval(() => {
          try {
            ws.send("ping");
          } catch (err) {
            console.error("[useFixtureSocket] Ping send failed:", err);
          }
        }, PING_INTERVAL_MS);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === "fixture_update") {
            onUpdateRef.current && onUpdateRef.current(data);
          }
        } catch (err) {
          console.error("[useFixtureSocket] Failed to parse message:", err);
        }
      };
      ws.onclose = () => {
        socketHealthy = false;
        clearInterval(pingTimer);
        startPolling();
        scheduleReconnect();
      };
      ws.onerror = (err) => {
        console.error("[useFixtureSocket] Socket error:", err);
        socketHealthy = false;
        startPolling();
        try {
          ws.close();
        } catch (closeErr) {
          console.error("[useFixtureSocket] Close after error failed:", closeErr);
        }
      };
    };

    const scheduleReconnect = () => {
      if (stopped) return;
      retry = Math.min(retry + 1, MAX_RETRY_EXPONENT);
      const delay = Math.min(BASE_RECONNECT_DELAY_MS * 2 ** retry, MAX_RECONNECT_DELAY_MS);
      setTimeout(connect, delay);
    };

    connect();

    return () => {
      stopped = true;
      clearInterval(pingTimer);
      stopPolling();
      try {
        ws && ws.close();
      } catch (err) {
        console.error("[useFixtureSocket] Cleanup close failed:", err);
      }
    };
  }, []);
}
