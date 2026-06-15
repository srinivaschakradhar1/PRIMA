import {
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  LinearProgress,
  Box,
} from '@mui/material';
import { Link } from 'react-router-dom';
import type { EquipmentStatusItem } from '@/models/types';
import StatusChip from '@/components/common/StatusChip';
import EmptyState from '@/components/common/EmptyState';

interface CriticalEquipmentTableProps {
  equipment?: EquipmentStatusItem[];
}

export default function CriticalEquipmentTable({ equipment }: CriticalEquipmentTableProps) {
  const critical = (equipment ?? [])
    .filter((item) => ['HIGH', 'CRITICAL'].includes((item.risk_of_failure ?? '').toUpperCase()))
    .sort((a, b) => a.health_score - b.health_score)
    .slice(0, 8);

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Top Critical Equipment
        </Typography>
        {critical.length === 0 ? (
          <EmptyState
            title="No high-risk equipment"
            description="Everything is currently within normal risk thresholds."
          />
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Equipment</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Health Score</TableCell>
                  <TableCell>Risk</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {critical.map((item) => (
                  <TableRow
                    key={item.equipment_id}
                    component={Link}
                    to={`/equipment/${item.equipment_id}`}
                    sx={{
                      textDecoration: 'none',
                      cursor: 'pointer',
                      '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                    }}
                  >
                    <TableCell sx={{ color: 'text.primary', fontWeight: 600 }}>
                      {item.equipment_name}
                    </TableCell>
                    <TableCell>
                      <StatusChip kind="status" value={item.status} />
                    </TableCell>
                    <TableCell sx={{ minWidth: 140 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={item.health_score}
                          sx={{ flexGrow: 1, height: 6 }}
                          color={item.health_score < 40 ? 'error' : item.health_score < 70 ? 'warning' : 'secondary'}
                        />
                        <Typography variant="caption" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                          {item.health_score}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <StatusChip kind="risk" value={item.risk_of_failure} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );
}
