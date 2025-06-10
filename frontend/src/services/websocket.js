const W3CWebSocket = WebSocket;

const ws = new W3CWebSocket('ws://localhost:8001/ws/logs/32');

ws.onopen = () => {
  console.log('WebSocket connection established');
};

ws.onmessage = (event) => {
  try {
    const data = JSON.parse(event.data); // Try to parse as JSON
    console.log('Received JSON:', data);
    // Handle the data (e.g., update UI with data.message)
  } catch (e) {
    console.warn('Received non-JSON message:', event.data);
    // Handle non-JSON case if needed
  }
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

export default ws;