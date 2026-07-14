from odoo import fields, models


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

    # TODO: "Test Connection" button per docs/architecture.md section 5.2 —
    # should call _get_monnify_client()._get_token() and toast success/failure.

    def _get_monnify_client(self):
        """Single place every other component gets a configured MonnifyClient.

        TODO: implement per docs/architecture.md section 5.2 — read the
        ir.config_parameter values above and return a services.monnify_client
        .MonnifyClient instance.
        """
        raise NotImplementedError
