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
import type { Alert } from '@/models/types';
import StatusChip from '@/components/common/StatusChip';
import EmptyState from '@/components/common/EmptyState';
import { formatDateTime } from '@/utils/format';
import NotificationsActiveOutlinedIcon from '@mui/icons-material/NotificationsActiveOutlined';

interface CriticalAlertsTableProps {
  alerts: Alert[];
}

export default function CriticalAlertsTable({ alerts }: CriticalAlertsTableProps) {
  const navigate = useNavigate();

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Active Alerts
        </Typography>
        {alerts.length === 0 ? (
          <EmptyState
            icon={<NotificationsActiveOutlinedIcon sx={{ fontSize: 32, opacity: 0.4 }} />}
            title="No active alerts"
            description="All equipment is operating within expected thresholds."
          />
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Severity</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Equipment</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Raised</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alerts.map((alert) => (
                  <TableRow
                    key={alert.id}
                    hover
                    onClick={() => navigate(`/equipment/${alert.equipment_id}`)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>
                      <StatusChip kind="risk" value={alert.severity} />
                    </TableCell>
                    <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.75rem' }}>
                      {alert.alert_type}
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{alert.equipment_name}</TableCell>
                    <TableCell>{alert.message}</TableCell>
                    <TableCell>{formatDateTime(alert.created_at)}</TableCell>
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
