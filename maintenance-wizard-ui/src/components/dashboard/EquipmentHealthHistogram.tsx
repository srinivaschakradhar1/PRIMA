import { Card, CardContent, Typography } from '@mui/material';
import Plot from 'react-plotly.js';
import type { EquipmentStatusItem } from '@/models/types';
import EmptyState from '@/components/common/EmptyState';

interface EquipmentHealthHistogramProps {
  equipment?: EquipmentStatusItem[];
}

export default function EquipmentHealthHistogram({ equipment }: EquipmentHealthHistogramProps) {
  const scores = (equipment ?? []).map((item) => item.health_score);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Health Score Distribution
        </Typography>
        {scores.length === 0 ? (
          <EmptyState title="No health scores yet" description="Health scores will appear once predictions are generated." />
        ) : (
          <Plot
            data={[
              {
                type: 'histogram',
                x: scores,
                marker: { color: '#FF6A3D', opacity: 0.85 },
                xbins: { start: 0, end: 100, size: 10 },
              },
            ]}
            layout={{
              autosize: true,
              height: 280,
              margin: { t: 10, b: 36, l: 36, r: 10 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#EAF1F5', size: 11 },
              xaxis: { title: { text: 'Health Score' }, gridcolor: '#27435A', range: [0, 100] },
              yaxis: { title: { text: 'Equipment Count' }, gridcolor: '#27435A' },
              bargap: 0.08,
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
