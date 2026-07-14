import base64

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(selection_add=[("monnify", "Monnify")], ondelete={"monnify": "set default"})
    monnify_api_key = fields.Char(string="Monnify API Key", groups="base.group_system")
    monnify_secret_key = fields.Char(string="Monnify Secret Key", groups="base.group_system")
    monnify_contract_code = fields.Char(string="Monnify Contract Code")
    monnify_webhook_secret = fields.Char(string="Monnify Webhook Secret", groups="base.group_system")
    monnify_use_sandbox = fields.Boolean(string="Use Sandbox", default=True)

    def _monnify_base_url(self):
        self.ensure_one()
        return "https://sandbox.monnify.com" if self.monnify_use_sandbox else "https://api.monnify.com"

    def _monnify_auth_header(self):
        self.ensure_one()
        if not (self.monnify_api_key and self.monnify_secret_key):
            raise ValidationError(_("Monnify API key and secret key are required."))
        token = base64.b64encode(f"{self.monnify_api_key}:{self.monnify_secret_key}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {token}"}

    def _monnify_access_token(self):
        self.ensure_one()
        response = requests.post(
            f"{self._monnify_base_url()}/api/v1/auth/login",
            headers=self._monnify_auth_header(),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("responseBody", {}).get("accessToken")

    def _monnify_request(self, method, endpoint, payload=None, params=None):
        self.ensure_one()
        access_token = self._monnify_access_token()
        headers = {"Authorization": "Bearer " + access_token, "Content-Type": "application/json"}
        response = requests.request(
            method,
            f"{self._monnify_base_url()}{endpoint}",
            json=payload,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("responseBody", {})

    def monnify_initialize_transaction(self, tx):
        self.ensure_one()
        if not self.monnify_contract_code:
            raise ValidationError(_("Monnify contract code is required."))
        payload = {
            "amount": tx.amount,
            "customerName": tx.partner_name or tx.partner_id.name or tx.reference,
            "customerEmail": tx.partner_email or tx.partner_id.email or "pos@example.com",
            "paymentReference": tx.reference,
            "paymentDescription": tx.reference,
            "currencyCode": tx.currency_id.name,
            "contractCode": self.monnify_contract_code,
            "paymentMethods": ["ACCOUNT_TRANSFER"],
            "redirectUrl": f"{tx.get_base_url()}/payment/status",
        }
        response = self._monnify_request("POST", "/api/v1/merchant/transactions/init-transaction", payload=payload)
        account_details = (response.get("accountDetails") or [{}])[0]
        tx.write(
            {
                "provider_reference": response.get("transactionReference") or tx.reference,
                "monnify_payment_reference": response.get("paymentReference") or tx.reference,
                "monnify_checkout_url": response.get("checkoutUrl"),
                "monnify_account_number": account_details.get("accountNumber"),
                "monnify_bank_name": account_details.get("bankName"),
                "monnify_expiry_datetime": response.get("expiryDate"),
            }
        )
        return response

    def monnify_fetch_status(self, payment_reference):
        self.ensure_one()
        return self._monnify_request(
            "GET",
            "/api/v2/merchant/transactions/query",
            params={"paymentReference": payment_reference},
        )

    @api.model
    def _get_compatible_providers(self, *args, **kwargs):
        providers = super()._get_compatible_providers(*args, **kwargs)
        if self.env.context.get("force_monnify_provider"):
            providers = providers.filtered(lambda p: p.code == "monnify")
        return providers
