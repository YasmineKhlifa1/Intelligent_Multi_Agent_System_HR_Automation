import React, { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';

const LogViewer = ({ userId }) => {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    if (userId) {
      const ws = new WebSocket(`ws://localhost:8001/ws/logs/${userId}`);
      ws.onmessage = (event) => {
        const log = JSON.parse(event.data);
        setLogs(prev => [...prev, log].slice(-10)); // Limite à 10 derniers logs
      };
      ws.onerror = (error) => console.error('WebSocket error:', error);
      return () => ws.close();
    }
  }, [userId]);

  return (
    <Box sx={{ mt: 4 }}>
      <Typography variant="h6">Logs en temps réel</Typography>
      <Box sx={{ maxHeight: 200, overflowY: 'auto', border: '1px solid #ccc', p: 2 }}>
        {logs.map((log, index) => (
          <Typography key={index}>{log.timestamp}: {log.message}</Typography>
        ))}
      </Box>
    </Box>
  );
};

export default LogViewer;