"""生成用于加密凭据的密钥。"""
from cryptography.fernet import Fernet


def main() -> None:
    print("SECRET_KEY=" + Fernet.generate_key().decode())
    print("JWT_SECRET_KEY=" + Fernet.generate_key().decode())


if __name__ == "__main__":
    main()
