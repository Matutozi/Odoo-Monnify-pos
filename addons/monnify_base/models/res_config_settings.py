from odoo import fields, models

from ..services.monnify_client import MonnifyClient


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    monnify_api_key = fields.Char(
        string="Monnify API Key",
        config_parameter="monnify_base.api_key",
    )
    monnify_secret_key = fields.Char(
        string="Monnify Secret Key",
        config_parameter="monnify_base.secret_key",
    )
    monnify_contract_code = fields.Char(
        string="Monnify Contract Code",
        config_parameter="monnify_base.contract_code",
    )
    monnify_base_url = fields.Char(
        string="Monnify Base URL",
        config_parameter="monnify_base.base_url",
        default="https://sandbox.monnify.com",
    )

    def _get_monnify_client(self):
        """Single place every other component gets a configured MonnifyClient."""
        icp = self.env["ir.config_parameter"].sudo()
        return MonnifyClient(
            api_key=icp.get_param("monnify_base.api_key"),
            secret_key=icp.get_param("monnify_base.secret_key"),
            contract_code=icp.get_param("monnify_base.contract_code"),
            base_url=icp.get_param(
                "monnify_base.base_url", "https://sandbox.monnify.com"
            ),
        )
