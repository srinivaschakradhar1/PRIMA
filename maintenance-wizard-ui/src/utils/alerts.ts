import type { Alert, EquipmentStatusItem } from '@/models/types';

// Alerts are derived client-side from equipment status data per the
// React UI spec: "Derived from: Equipment Status, Health Records, Prediction Results".

const RUL_THRESHOLD_DAYS = 30;

export function deriveAlertsFromStatus(equipment: EquipmentStatusItem[]): Alert[] {
  const alerts: Alert[] = [];

  for (const item of equipment) {
    const risk = (item.risk_of_failure ?? '').toUpperCase();

    if (item.status === 'FAILED') {
      alerts.push({
        id: `${item.equipment_id}-failed`,
        equipment_id: item.equipment_id,
        equipment_name: item.equipment_name,
        alert_type: 'PREDICTED FAILURE',
        severity: 'CRITICAL',
        message: `${item.equipment_name} is currently in FAILED status.`,
        created_at: new Date().toISOString(),
      });
    }

    if (risk === 'CRITICAL' || risk === 'HIGH') {
      alerts.push({
        id: `${item.equipment_id}-risk`,
        equipment_id: item.equipment_id,
        equipment_name: item.equipment_name,
        alert_type: 'PREDICTED FAILURE',
        severity: risk,
        message: `${item.equipment_name} shows ${risk.toLowerCase()} failure risk (health score ${item.health_score}).`,
        created_at: new Date().toISOString(),
      });
    }

    if (item.health_score < 40) {
      alerts.push({
        id: `${item.equipment_id}-health`,
        equipment_id: item.equipment_id,
        equipment_name: item.equipment_name,
        alert_type: 'RUL BELOW THRESHOLD',
        severity: item.health_score < 25 ? 'CRITICAL' : 'HIGH',
        message: `${item.equipment_name} health score has dropped to ${item.health_score}.`,
        created_at: new Date().toISOString(),
      });
    }
  }

  return alerts;
}

export { RUL_THRESHOLD_DAYS };
