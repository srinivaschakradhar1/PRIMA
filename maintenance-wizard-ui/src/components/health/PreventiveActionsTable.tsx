import {
  Card,
  CardContent,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { PreventiveAction } from '@/models/types';
import EmptyState from '@/components/common/EmptyState';

interface PreventiveActionsTableProps {
  actions: PreventiveAction[];
  equipmentName?: string;
}

export default function PreventiveActionsTable({ actions, equipmentName }: PreventiveActionsTableProps) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Preventive Actions{equipmentName ? ` — ${equipmentName}` : ''}
        </Typography>
        {actions.length === 0 ? (
          <EmptyState
            title="No preventive actions recommended"
            description="The prediction engine has not flagged any actions for this asset."
          />
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 80 }}>Priority</TableCell>
                  <TableCell>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {[...actions]
                  .sort((a, b) => a.priority - b.priority)
                  .map((action) => (
                    <TableRow key={action.priority}>
                      <TableCell>
                        <Chip
                          label={action.priority}
                          size="small"
                          color={action.priority === 1 ? 'primary' : 'default'}
                          sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                        />
                      </TableCell>
                      <TableCell>{action.action}</TableCell>
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
