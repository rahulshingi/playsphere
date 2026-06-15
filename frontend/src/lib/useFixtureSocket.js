import { useEffect, useRef } from "react";

/**
 * Subscribe to backend WebSocket and invoke onUpdate(payload) on every message.
 * Payload shape: { type: "fixture_update", event_id, fixture }
 */
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
      } catch (e) {
        scheduleReconnect();
        return;
      }
      ws.onopen = () => {
        retry = 0;
        pingTimer = setInterval(() => {
          try { ws.send("ping"); } catch (e) { /* ignore */ }
        }, 25000);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === "fixture_update") {
            onUpdateRef.current && onUpdateRef.current(data);
          }
        } catch (e) { /* ignore */ }
      };
      ws.onclose = () => {
        clearInterval(pingTimer);
        scheduleReconnect();
      };
      ws.onerror = () => {
        try { ws.close(); } catch (e) { /* ignore */ }
      };
    };

    const scheduleReconnect = () => {
      if (stopped) return;
      retry = Math.min(retry + 1, 6);
      setTimeout(connect, Math.min(1000 * 2 ** retry, 30000));
    };

    connect();

    return () => {
      stopped = true;
      clearInterval(pingTimer);
      try { ws && ws.close(); } catch (e) { /* ignore */ }
    };
  }, []);
}
