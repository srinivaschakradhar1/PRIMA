# Maintenance SOP: Converter Tilting Drive (BOF-003)

**Document No:** SOP-BOF-003-01
**Category:** Basic Oxygen Furnace
**Revision:** 1.0
**Applicable Equipment Manual:** MAN-BOF-003-01

## 1. Purpose

This SOP defines the standard maintenance practices, inspection checklist, and corrective
procedures for Converter Tilting Drive (BOF-003) to ensure reliable operation and to support
predictive maintenance and root-cause analysis activities.

## 2. Scope

Applicable to all maintenance personnel responsible for inspection, preventive maintenance,
and breakdown maintenance of Converter Tilting Drive units within the Basic Oxygen Furnace.

## 3. Safety Requirements

- Obtain work permit and complete LOTO before any intervention.
- Use PPE appropriate to the task (refer to equipment manual Section 6).
- Confirm isolation of electrical, hydraulic, pneumatic, and thermal energy sources.

## 4. Daily Operator Checks

- [ ] Verify tilt_torque_kNm is within normal operating range as per equipment manual.
- [ ] Verify gearbox_temperature_C is within normal operating range as per equipment manual.
- [ ] Verify motor_current_A is within normal operating range as per equipment manual.
- [ ] Verify tilt_angle_deg is within normal operating range as per equipment manual.
- [ ] Verify vibration_mm_s is within normal operating range as per equipment manual.
- [ ] Visual inspection for abnormal noise, leakage, or vibration.
- [ ] Check lubrication levels where applicable.

## 5. Preventive Maintenance Schedule

| Task | Frequency | Responsibility |
|---|---|---|
| Visual inspection and cleaning | Daily | Operator / Maintenance Technician |
| Lubrication / grease replenishment | Monthly | Maintenance Technician |
| Vibration / thermal condition monitoring survey | Weekly | Condition Monitoring Team |
| Bolt torque / alignment check | Half-Yearly | Maintenance Technician |
| Major overhaul / component replacement | Yearly | Maintenance Team + OEM/Vendor (if required) |

## 6. Condition-Based Maintenance Triggers

Maintenance intervention shall be planned when any of the following conditions are observed
in the sensor data summaries or anomaly alert system:

- Sustained deviation greater than 15% from baseline on any monitored parameter (Warning level).
- Deviation greater than 40% from baseline (Critical level) - immediate inspection required.
- Two or more consecutive "Warning" status flags on the same sensor within a 7-day period.
- Health Index falling below 70%.

## 7. Breakdown / Corrective Maintenance Procedures by Failure Mode

### 1. Gearbox bearing wear

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating gearbox bearing wear.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-BOF-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 2. Drive motor overload

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating drive motor overload.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-BOF-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 3. Trunnion ring wear

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating trunnion ring wear.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-BOF-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 4. Brake fault

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating brake fault.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-BOF-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.


## 8. Spare Parts and Procurement

Refer to spare parts master record (part IDs prefixed SP-BOF-003) for stock levels,
reorder points, and procurement lead times. Maintenance planning should account for lead
times when scheduling non-emergency replacements.

## 9. Documentation Requirements

All maintenance activities shall be logged in the Maintenance History register with:
work order number, date, maintenance type, failure mode (if applicable), root cause,
corrective action, parts replaced, technician, downtime, and cost.

## 10. Revision History

| Rev | Date | Description | Approved By |
|---|---|---|---|
| 1.0 | 2024-01-01 | Initial issue (synthetic dataset) | Plant Maintenance Department |
