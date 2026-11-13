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

    def write(self, vals):
        res = super().write(vals)
        if 'unit_amount' in vals:
            self.filtered('global_leave_id')._sync_public_holiday_skip()
        return res

    def _sync_public_holiday_skip(self):
        """Upstream forbids deleting a public-holiday entry, so setting its
        hours to 0 is how someone says "worked that day" (e.g. abroad).
        Remember it, so regenerating the employee's holiday entries
        (calendar change, unarchive) does not bring the hours back; giving
        the hours back clears the mark."""
        # sudo: bookkeeping of an edit the user is already allowed to make.
        Skip = self.env['public.holiday.timesheet.skip'].sudo()
        zeroed = self.filtered(lambda line: not line.unit_amount and line.employee_id)
        restored = self - zeroed
        if restored:
            Skip.search([
                ('employee_id', 'in', restored.employee_id.ids),
                ('date', 'in', list(set(restored.mapped('date')))),
            ]).filtered(lambda s: (s.employee_id, s.date) in {(l.employee_id, l.date) for l in restored}).unlink()
        if zeroed:
            existing = {(s.employee_id.id, s.date) for s in Skip.search([
                ('employee_id', 'in', zeroed.employee_id.ids),
                ('date', 'in', list(set(zeroed.mapped('date')))),
            ])}
            vals_list = []
            for line in zeroed:
                key = (line.employee_id.id, line.date)
                if key not in existing:
                    existing.add(key)
                    vals_list.append({'employee_id': key[0], 'date': key[1], 'global_leave_id': line.global_leave_id.id})
            Skip.create(vals_list)
