import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import type { EquipmentListItem } from '@/models/types';
import StatusChip from '@/components/common/StatusChip';
import EquipmentHealthBadge from './EquipmentHealthBadge';
import EmptyState from '@/components/common/EmptyState';

interface EquipmentTableProps {
  equipment: EquipmentListItem[];
}

export default function EquipmentTable({ equipment }: EquipmentTableProps) {
  const navigate = useNavigate();

  if (equipment.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <EmptyState
          title="No equipment matches these filters"
          description="Try clearing one or more filters to broaden the results."
        />
      </Paper>
    );
  }

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Code</TableCell>
            <TableCell>Name</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Criticality</TableCell>
            <TableCell>Health Score</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Location</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {equipment.map((item) => (
            <TableRow
              key={item.id}
              hover
              onClick={() => navigate(`/equipment/${item.id}`)}
              sx={{ cursor: 'pointer' }}
            >
              <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {item.equipment_code}
              </TableCell>
              <TableCell sx={{ fontWeight: 600 }}>{item.equipment_name}</TableCell>
              <TableCell>{item.equipment_type ?? '—'}</TableCell>
              <TableCell>
                {item.criticality ? (
                  <StatusChip kind="criticality" value={item.criticality} />
                ) : (
                  '—'
                )}
              </TableCell>
              <TableCell>
                <EquipmentHealthBadge score={item.health_score} />
              </TableCell>
              <TableCell>
                <StatusChip kind="status" value={item.status} />
              </TableCell>
              <TableCell>{item.location_in_plant ?? '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
