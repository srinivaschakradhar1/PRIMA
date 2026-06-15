import { Card, CardContent, Typography } from '@mui/material';
import Plot from 'react-plotly.js';

interface HealthScoreGaugeProps {
  healthScore?: number;
  risk?: string;
}

const riskHex: Record<string, string> = {
  LOW: '#3DDC97',
  MEDIUM: '#FFB454',
  HIGH: '#FF6A3D',
  CRITICAL: '#E84855',
};

export default function HealthScoreGauge({ healthScore = 0, risk = 'LOW' }: HealthScoreGaugeProps) {
  const color = riskHex[risk?.toUpperCase()] ?? '#3DDC97';

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Health Score
        </Typography>
        <Plot
          data={[
            {
              type: 'indicator',
              mode: 'gauge+number',
              value: healthScore,
              number: { font: { family: 'JetBrains Mono, monospace', size: 36, color: '#EAF1F5' } },
              gauge: {
                axis: { range: [0, 100], tickcolor: '#9FB3C2' },
                bar: { color },
                bgcolor: 'transparent',
                bordercolor: '#27435A',
                steps: [
                  { range: [0, 40], color: 'rgba(232,72,85,0.15)' },
                  { range: [40, 70], color: 'rgba(255,180,84,0.15)' },
                  { range: [70, 100], color: 'rgba(61,220,151,0.15)' },
                ],
              },
            },
          ]}
          layout={{
            autosize: true,
            height: 220,
            margin: { t: 20, b: 10, l: 30, r: 30 },
            paper_bgcolor: 'transparent',
            font: { color: '#EAF1F5' },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </CardContent>
    </Card>
  );
}
