
from yaml import load, Loader

with open("config.yml", 'r', encoding="utf8") as _fs:
    config = load(_fs, Loader)

#
#
db_path: str = config.get("db_path", "users.db")

#
#
token: str = config.get("token")
qiwi_token: str = config.get("qiwi_token")
channel_pass_id: int = config.get("channel_pass_id", 0)

#
#
payment_theme: str = config.get("payment_theme", "")
payment_currency: str = config.get("payment_currency", "RUB")

#
#
home_button_text: str = config.get("home_button_text", "menu")

#
#
before_start_text: str = config.get("before_start_text")

#
#
start_text: str = config.get("start_text", "No start text")
start_button_text: str = config.get("start_button_text", "start")

info_button_text: str = config.get("info_button_text", "information")

#
#
select_plan_text: str = config.get("select_plan_text")
select_plan_format: str = config.get("select_plan_format")
select_plan_products: dict = config.get("select_plan_products", {})

#
#
payment_check_text: str = config.get("payment_check_text", "check")
payment_notyet_text: str = config.get("payment_notyet_text", "payment is not confirmed yet")
payment_cancel_text: str = config.get("payment_cancel_text", "cancel")
payment_proceed_text: str = config.get("payment_proceed_text", "")
payment_success_text: str = config.get("payment_success_text", "")
payment_expiried_text: str = config.get("payment_expiried_text", "")
payment_canceled_text: str = config.get("payment_canceled_text", "")
payment_checkagain_text: str = config.get("payment_checkagain_text", "check again")

#
#
info_subscriptions_text: str = config.get("info_subscriptions_text")
info_subscriptions_nosub: str = config.get("info_subscriptions_nosub")
info_subscriptions_format: str = config.get("info_subscriptions_format")
info_subscription_forever: str = config.get("info_subscription_forever")

#
#
expiried_text: str = config.get("expiried_text", "")
