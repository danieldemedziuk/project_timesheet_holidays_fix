# -*- coding: utf-8 -*-
{
    'name': 'Project Timesheet Holidays Fix',
    'version': '17.0.1.1.0',
    'author': 'DSquare Net',
    'license': 'LGPL-3',
    'sequence': 145,
    'summary': 'Fixes duplicate/orphaned time-off placeholder entries created by project_timesheet_holidays',
    'description': """
Project Timesheet Holidays Fix
===============================
project_timesheet_holidays (Odoo Enterprise) auto-generates zero-amount
"Time Off (x/y)" placeholder entries on account.analytic.line whenever an
employee takes leave or a public holiday is scheduled. Two bugs in that
module let these placeholders accumulate as duplicates/orphans instead of
staying one-per-employee-per-day:

1. hr.leave.write() cleared the holiday_id link on its own timesheet lines,
   then tried to re-read that same (now-invalidated) relation to build the
   list of lines to delete - always finding it empty, so the line meant to
   be removed was left behind forever with a null holiday_id, invisible to
   every future cleanup/dedup search that filters on holiday_id being set.
2. hr.employee._create_future_public_holidays_timesheets() read the day-by-
   day work-hours data with a key one level too shallow when building the
   "(x/y)" label, always producing "(x/0)" - a labeling bug that also
   points at the underlying per-employee/calendar computation being wrong.

This module:
- Fixes hr.leave.write() to capture the timesheet lines before clearing
  their link, matching the (correct) pattern already used by this same
  Enterprise module in action_refuse/_action_user_cancel/_force_cancel.
- Fixes the indexing bug in _create_future_public_holidays_timesheets.
- Adds a hard database-level safeguard: a uniqueness constraint on
  (holiday_id, employee_id, date) and (global_leave_id, employee_id, date)
  on account.analytic.line, so no future bug - in this module, in an
  Enterprise upgrade, or anywhere else - can silently recreate this mess.
  PostgreSQL treats NULL as distinct in unique constraints, so this only
  ever constrains actual time-off placeholder rows, never regular
  timesheet/cost lines.
- Backfills missing public-holiday entries (daily cron, plus a one-time
  run from 2026-11-11 on upgrade): upstream only generates them when the
  holiday, employee or calendar is created/changed. Days with booked work,
  an approved sheet or an existing holiday entry are skipped;
  holiday hours set to 0 are remembered in
  public.holiday.timesheet.skip and not regenerated.
- One-time cleanup (pre_init_hook, so it runs before the constraint above
  is created): removes orphaned placeholder rows left behind by bug #1,
  and de-duplicates the handful of remaining true duplicates.
""",
    'category': 'Human Resources',
    'depends': [
        'project_timesheet_holidays',
        'hr_timesheet_sheet',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/public_holiday_timesheet_skip_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'auto_install': False,
    'installable': True,
    'application': False,
}
