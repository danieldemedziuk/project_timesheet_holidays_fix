# -*- coding: utf-8 -*-

from odoo import models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    # PostgreSQL treats NULL as distinct from any other value in a unique
    # constraint, so these only ever constrain the actual time-off
    # placeholder rows project_timesheet_holidays creates (the only code
    # that ever sets holiday_id/global_leave_id) - every regular timesheet,
    # RCP posting, or financial-close line has both null and is completely
    # unaffected. This is the real, future-proof fix: even if another bug
    # (in this module, in a future Enterprise upgrade, or anywhere else)
    # tries to create a second placeholder for the same leave/employee/day,
    # the database itself now refuses it, instead of silently accumulating
    # more of the mess pre_init_hook cleaned up on install.
    _sql_constraints = [
        ('holiday_timesheet_unique', 'unique(holiday_id, employee_id, date)',
         'A time-off timesheet entry already exists for this leave, employee and day.'),
        ('global_leave_timesheet_unique', 'unique(global_leave_id, employee_id, date)',
         'A time-off timesheet entry already exists for this public holiday, employee and day.'),
    ]
