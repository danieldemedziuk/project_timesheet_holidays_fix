# -*- coding: utf-8 -*-

from odoo import models


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def write(self, vals):
        """Fixes an order-of-operations bug in project_timesheet_holidays'
        own write(): it cleared timesheet_ids.holiday_id and THEN re-read
        leave.timesheet_ids to know what to unlink - but timesheet_ids is a
        non-stored One2many keyed on holiday_id, so clearing that FK first
        makes the re-read always come back empty. The line that was
        supposed to be deleted survives forever with holiday_id=NULL,
        invisible to every future cleanup search that filters on
        holiday_id being set.

        super().write() below still runs that buggy code (it's earlier in
        the MRO chain) - it DOES successfully clear holiday_id before
        failing to collect anything to unlink, so we can't just re-read
        timesheet_ids afterward either, it would already be empty for the
        same reason. Capture the recordset up front, before anything
        touches the FK, exactly like the (correct) sibling methods in the
        same module already do - action_refuse, _action_user_cancel,
        _force_cancel - then decide what to remove using the post-write
        state of number_of_days.
        """
        pre_timesheets = {
            leave.id: leave.sudo().timesheet_ids
            for leave in self
            if leave.sudo().timesheet_ids
        }

        res = super().write(vals)

        timesheets_to_remove = self.env['account.analytic.line']
        for leave in self:
            if leave.id in pre_timesheets and leave.number_of_days == 0:
                timesheets_to_remove |= pre_timesheets[leave.id]

        if timesheets_to_remove:
            # Some of these may already have holiday_id cleared by the
            # buggy super() call above; re-clearing and unlinking is
            # idempotent either way.
            timesheets_to_remove = timesheets_to_remove.exists()
            timesheets_to_remove.holiday_id = False
            timesheets_to_remove.unlink()
        return res
