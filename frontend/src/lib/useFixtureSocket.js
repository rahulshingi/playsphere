import { useEffect, useRef } from "react";

/**
 * Subscribe to backend WebSocket and invoke onUpdate(payload) on every message.
 * Payload shape: { type: "fixture_update", event_id, fixture }
 */
const PING_INTERVAL_MS = 25000;
const MAX_RECONNECT_DELAY_MS = 30000;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RETRY_EXPONENT = 6;

export default function useFixtureSocket(onUpdate) {
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => { onUpdateRef.current = onUpdate; }, [onUpdate]);

  useEffect(() => {
    const backend = process.env.REACT_APP_BACKEND_URL || "";
    const wsUrl = backend.replace(/^http/, "ws") + "/api/ws";
    let ws;
    let pingTimer;
    let stopped = false;
    let retry = 0;

    const connect = () => {
      if (stopped) return;
      try {
        ws = new WebSocket(wsUrl);
      } catch (err) {
        console.error("[useFixtureSocket] WebSocket constructor failed:", err);
        scheduleReconnect();
        return;
      }
      ws.onopen = () => {
        retry = 0;
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
        clearInterval(pingTimer);
        scheduleReconnect();
      };
      ws.onerror = (err) => {
        console.error("[useFixtureSocket] Socket error:", err);
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
      try {
        ws && ws.close();
      } catch (err) {
        console.error("[useFixtureSocket] Cleanup close failed:", err);
      }
    };
  }, []);
}
