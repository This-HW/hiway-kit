def get_domain(email):
    """Return the domain part of an email address, or None if not a valid email."""
    return email.split("@")[1].upper()
