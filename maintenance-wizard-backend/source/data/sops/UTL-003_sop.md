# Maintenance SOP: Generator (UTL-003)

**Document No:** SOP-UTL-003-01
**Category:** Utility - Power Plant
**Revision:** 1.0
**Applicable Equipment Manual:** MAN-UTL-003-01

## 1. Purpose

This SOP defines the standard maintenance practices, inspection checklist, and corrective
procedures for Generator (UTL-003) to ensure reliable operation and to support
predictive maintenance and root-cause analysis activities.

## 2. Scope

Applicable to all maintenance personnel responsible for inspection, preventive maintenance,
and breakdown maintenance of Generator units within the Utility - Power Plant.

## 3. Safety Requirements

- Obtain work permit and complete LOTO before any intervention.
- Use PPE appropriate to the task (refer to equipment manual Section 6).
- Confirm isolation of electrical, hydraulic, pneumatic, and thermal energy sources.

## 4. Daily Operator Checks

- [ ] Verify winding_temperature_C is within normal operating range as per equipment manual.
- [ ] Verify output_voltage_V is within normal operating range as per equipment manual.
- [ ] Verify output_current_A is within normal operating range as per equipment manual.
- [ ] Verify bearing_temperature_C is within normal operating range as per equipment manual.
- [ ] Verify vibration_mm_s is within normal operating range as per equipment manual.
- [ ] Visual inspection for abnormal noise, leakage, or vibration.
- [ ] Check lubrication levels where applicable.

## 5. Preventive Maintenance Schedule

| Task | Frequency | Responsibility |
|---|---|---|
| Visual inspection and cleaning | Daily | Operator / Maintenance Technician |
| Lubrication / grease replenishment | Weekly | Maintenance Technician |
| Vibration / thermal condition monitoring survey | Weekly | Condition Monitoring Team |
| Bolt torque / alignment check | Quarterly | Maintenance Technician |
| Major overhaul / component replacement | Yearly | Maintenance Team + OEM/Vendor (if required) |

## 6. Condition-Based Maintenance Triggers

Maintenance intervention shall be planned when any of the following conditions are observed
in the sensor data summaries or anomaly alert system:

- Sustained deviation greater than 15% from baseline on any monitored parameter (Warning level).
- Deviation greater than 40% from baseline (Critical level) - immediate inspection required.
- Two or more consecutive "Warning" status flags on the same sensor within a 7-day period.
- Health Index falling below 70%.

## 7. Breakdown / Corrective Maintenance Procedures by Failure Mode

### 1. Winding insulation degradation

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating winding insulation degradation.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-UTL-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 2. Bearing failure

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating bearing failure.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-UTL-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 3. Exciter fault

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating exciter fault.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-UTL-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.

### 4. Cooling fan failure

**Trigger:** Condition monitoring alert, fault code, or operator observation indicating cooling fan failure.

**Procedure:**
1. Notify shift supervisor and raise a maintenance work order.
2. Isolate equipment per LOTO procedure if shutdown is required.
3. Inspect the relevant component(s) associated with this failure mode.
4. Carry out corrective action (repair/replace as required) per equipment manual MAN-UTL-003-01.
5. Perform functional test and confirm sensor readings return to normal range.
6. Record findings, root cause, parts used, and downtime in the maintenance history log.
7. Re-commission equipment and inform production/shift team.


## 8. Spare Parts and Procurement

Refer to spare parts master record (part IDs prefixed SP-UTL-003) for stock levels,
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
