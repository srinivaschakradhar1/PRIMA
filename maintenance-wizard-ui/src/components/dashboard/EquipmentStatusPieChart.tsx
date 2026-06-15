import { Card, CardContent, Typography } from '@mui/material';
import Plot from 'react-plotly.js';
import type { EquipmentStatusSummary } from '@/models/types';
import { statusColors } from '@/theme';
import EmptyState from '@/components/common/EmptyState';

interface EquipmentStatusPieChartProps {
  summary?: EquipmentStatusSummary;
}

export default function EquipmentStatusPieChart({ summary }: EquipmentStatusPieChartProps) {
  const entries = summary
    ? (Object.entries(summary) as [keyof EquipmentStatusSummary, number][]).filter(
        ([, value]) => value > 0
      )
    : [];

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Equipment Status Distribution
        </Typography>
        {entries.length === 0 ? (
          <EmptyState title="No status data yet" description="Waiting on equipment status feed." />
        ) : (
          <Plot
            data={[
              {
                type: 'pie',
                labels: entries.map(([key]) => key.replace('_', ' ')),
                values: entries.map(([, value]) => value),
                hole: 0.55,
                marker: {
                  colors: entries.map(([key]) => statusColors[key] ?? '#7AA2C2'),
                },
                textinfo: 'label+value',
                textfont: { family: 'JetBrains Mono, monospace', size: 11, color: '#EAF1F5' },
                hoverinfo: 'label+percent',
              },
            ]}
            layout={{
              autosize: true,
              height: 280,
              margin: { t: 10, b: 10, l: 10, r: 10 },
              showlegend: true,
              legend: { orientation: 'h', y: -0.1, font: { color: '#9FB3C2', size: 11 } },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#EAF1F5' },
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
