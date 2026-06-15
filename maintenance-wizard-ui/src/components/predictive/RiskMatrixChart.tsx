import { Card, CardContent, Typography } from '@mui/material';
import Plot from 'react-plotly.js';
import { useNavigate } from 'react-router-dom';
import type { EquipmentStatusItem } from '@/models/types';
import EmptyState from '@/components/common/EmptyState';
import { riskColors } from '@/theme';

interface RiskMatrixChartProps {
  equipment?: EquipmentStatusItem[];
}

const riskOrder: Record<string, number> = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

export default function RiskMatrixChart({ equipment }: RiskMatrixChartProps) {
  const navigate = useNavigate();
  const items = equipment ?? [];

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Health Score vs. Risk Level
        </Typography>
        {items.length === 0 ? (
          <EmptyState title="No equipment data" description="Predictive insights will appear once equipment data loads." />
        ) : (
          <Plot
            data={[
              {
                type: 'scatter',
                mode: 'markers',
                x: items.map((i) => i.health_score),
                y: items.map((i) => riskOrder[(i.risk_of_failure ?? '').toUpperCase()] ?? 0),
                text: items.map((i) => i.equipment_name),
                customdata: items.map((i) => i.equipment_id),
                marker: {
                  size: 12,
                  color: items.map((i) => riskColors[(i.risk_of_failure ?? '').toUpperCase()] ?? '#7AA2C2'),
                  line: { color: '#0B1F2A', width: 1 },
                },
                hovertemplate: '%{text}<br>Health: %{x}<extra></extra>',
              },
            ]}
            layout={{
              autosize: true,
              height: 320,
              margin: { t: 10, b: 40, l: 90, r: 20 },
              paper_bgcolor: 'transparent',
              plot_bgcolor: 'transparent',
              font: { color: '#EAF1F5', size: 11 },
              xaxis: { title: { text: 'Health Score' }, range: [0, 100], gridcolor: '#27435A' },
              yaxis: {
                title: { text: 'Risk Level' },
                tickmode: 'array',
                tickvals: [1, 2, 3, 4],
                ticktext: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
                range: [0.5, 4.5],
                gridcolor: '#27435A',
              },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%' }}
            useResizeHandler
            onClick={(e) => {
              const point = e.points?.[0];
              const id = point?.customdata as unknown as string | undefined;
              if (id) navigate(`/equipment/${id}`);
            }}
          />
        )}
      </CardContent>
    </Card>
  );
}
