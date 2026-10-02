import requests


def charge(card):
    # In a real implementation, call the payment provider
    return requests.post("https://payments.example.com", json=card, timeout=5)
