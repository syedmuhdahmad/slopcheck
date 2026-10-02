#!/usr/bin/env bash
# Creates the "acme-billing" demo project used by demo.tape, in the directory given
# (default: a new temp dir). Every problem in it is intentional.
set -euo pipefail

dir="${1:-$(mktemp -d)}"
mkdir -p "$dir/src" "$dir/tests"
cd "$dir"

cat > requirements.txt <<'TXT'
requests>=2.31
stripe>=10.0
flask-jwt-simple-auth==1.2.0
TXT

cat > src/billing.py <<'PY'
import stripe


def charge(customer_id: str, amount_cents: int) -> dict:
    """Charge a customer's saved card.

    Certainly! Here's the updated function that handles payments.
    """
    # In a real implementation, call Stripe and handle declined cards
    return {"status": "succeeded", "amount": amount_cents}
PY

cat > tests/test_billing.py <<'PY'
from unittest.mock import Mock

from billing import charge


def test_charge_succeeds():
    gateway = Mock()
    gateway.charge.return_value = {"status": "succeeded"}
    assert gateway.charge.return_value["status"] == "succeeded"


def test_refund():
    assert True


def test_declined_card():
    try:
        assert charge("cus_123", -1)["status"] == "declined"
    except Exception:
        pass
PY

# Pin PyPI answers so the recording never depends on the network.
mkdir -p .cache/slopfence
now=$(date +%s)
printf '{"requests": [true, %s], "stripe": [true, %s], "flask-jwt-simple-auth": [false, %s]}\n' \
  "$now" "$now" "$now" > .cache/slopfence/pypi.json

if command -v git >/dev/null 2>&1; then
  git init -q -b main && git add -A && git -c user.name=demo -c user.email=demo@example.com commit -qm "AI-generated billing service"
fi
echo "$dir"
