import type { ReactNode } from 'react';
import DashboardIcon from '@mui/icons-material/SpaceDashboardOutlined';
import EquipmentIcon from '@mui/icons-material/PrecisionManufacturingOutlined';
import KnowledgeIcon from '@mui/icons-material/MenuBookOutlined';
import AssistantIcon from '@mui/icons-material/AutoAwesomeOutlined';
import PredictiveIcon from '@mui/icons-material/QueryStatsOutlined';
import AlertsIcon from '@mui/icons-material/NotificationsActiveOutlined';

export interface MenuItem {
  id: string;
  label: string;
  icon: ReactNode;
  route: string;
}

export const menuItems: MenuItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <DashboardIcon />, route: '/dashboard' },
  { id: 'equipment', label: 'Equipment', icon: <EquipmentIcon />, route: '/equipment' },
  { id: 'knowledge', label: 'Knowledge Base', icon: <KnowledgeIcon />, route: '/knowledge' },
  { id: 'assistant', label: 'AI Maintenance Assistant', icon: <AssistantIcon />, route: '/assistant' },
  { id: 'predictive', label: 'Predictive Maintenance', icon: <PredictiveIcon />, route: '/predictive' },
  { id: 'alerts', label: 'System Alerts', icon: <AlertsIcon />, route: '/alerts' },
];
