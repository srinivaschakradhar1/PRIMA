import { Card, CardContent, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState } from 'react';
import Plot from 'react-plotly.js';
import type { SensorTrendPoint } from '@/models/types';
import EmptyState from '@/components/common/EmptyState';

interface SensorTrendChartProps {
  // Sensor history is not exposed by a documented GET endpoint yet; pass data
  // in when a `/sensor-readings` retrieval endpoint becomes available.
  series?: Record<string, SensorTrendPoint[]>;
}

const sensorTypes = ['TEMP', 'VIBRATION', 'PRESSURE', 'RPM', 'CURRENT'];

export default function SensorTrendChart({ series }: SensorTrendChartProps) {
  const [sensorType, setSensorType] = useState(sensorTypes[0]);
  const points = series?.[sensorType] ?? [];

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="subtitle2" color="text.secondary">
            Sensor Trend
          </Typography>
          <TextField
            select
            size="small"
            value={sensorType}
            onChange={(e) => setSensorType(e.target.value)}
            sx={{ minWidth: 140 }}
          >
            {sensorTypes.map((type) => (
              <MenuItem key={type} value={type}>
                {type}
              </MenuItem>
            ))}
          </TextField>
        </Stack>

        {points.length === 0 ? (
          <EmptyState
            title="No sensor history available"
            description="Connect a sensor-reading history endpoint to populate this chart with live trend data."
          />
        ) : (
          <Plot
            data={[
              {
                type: 'scatter',
                mode: 'lines',
                x: points.map((p) => p.timestamp),
                y: points.map((p) => p.value),
                line: { color: '#FF6A3D' },
              },
            ]}
            layout={{
              autosize: true,
              height: 280,
              margin: { t: 10, b: 36, l: 44, r: 10 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#EAF1F5', size: 11 },
              xaxis: { gridcolor: '#27435A' },
              yaxis: { title: { text: sensorType }, gridcolor: '#27435A' },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
            useResizeHandler
          />
        )}
      </CardContent>
    </Card>
  );
}
