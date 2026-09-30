"""Password-reset OTP hashing helpers — codes are never stored in plaintext."""
import bcrypt


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()


def check_otp(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.checkpw(otp.encode(), otp_hash.encode())
    except (ValueError, TypeError):
        return False
