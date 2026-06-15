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
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { EquipmentStatusItem } from '@/models/types';
import StatusChip from '@/components/common/StatusChip';
import EmptyState from '@/components/common/EmptyState';

interface RULRankingTableProps {
  equipment?: EquipmentStatusItem[];
}

export default function RULRankingTable({ equipment }: RULRankingTableProps) {
  const navigate = useNavigate();
  const items = [...(equipment ?? [])].sort((a, b) => a.health_score - b.health_score).slice(0, 10);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Equipment Ranked by Health (Lowest First)
        </Typography>
        {items.length === 0 ? (
          <EmptyState title="No equipment data" description="Rankings will appear once equipment data loads." />
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Equipment</TableCell>
                  <TableCell>Health</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Risk</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow
                    key={item.equipment_id}
                    hover
                    onClick={() => navigate(`/equipment/${item.equipment_id}`)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell sx={{ fontWeight: 600 }}>{item.equipment_name}</TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                      {item.health_score}
                    </TableCell>
                    <TableCell>
                      <StatusChip kind="status" value={item.status} />
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
