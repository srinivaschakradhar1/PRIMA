import { createBrowserRouter, Navigate } from 'react-router-dom';
import AppLayout from '@/components/layout/AppLayout';
import DashboardPage from '@/pages/DashboardPage';
import PlantPage from '@/pages/PlantPage';
import EquipmentPage from '@/pages/EquipmentPage';
import EquipmentDetailsPage from '@/pages/EquipmentDetailsPage';
import KnowledgeBasePage from '@/pages/KnowledgeBasePage';
import AssistantPage from '@/pages/AssistantPage';
import EquipmentHealthPage from '@/pages/EquipmentHealthPage';
import PredictiveMaintenancePage from '@/pages/PredictiveMaintenancePage';
import AlertsPage from '@/pages/AlertsPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'plants', element: <PlantPage /> },
      { path: 'equipment', element: <EquipmentPage /> },
      { path: 'equipment/:equipmentId', element: <EquipmentDetailsPage /> },
      { path: 'knowledge', element: <KnowledgeBasePage /> },
      { path: 'assistant', element: <AssistantPage /> },
      { path: 'health', element: <EquipmentHealthPage /> },
      { path: 'predictive', element: <PredictiveMaintenancePage /> },
      { path: 'alerts', element: <AlertsPage /> },
      { path: '*', element: <Navigate to="/dashboard" replace /> },
    ],
  },
]);
